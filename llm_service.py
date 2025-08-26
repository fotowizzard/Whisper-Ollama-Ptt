#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Сервис для работы с LLM через Ollama
"""

import requests
import time
import json
import threading
from typing import Optional, Dict, Any, List, Callable
from dataclasses import dataclass
from config import OllamaConfig
from logging_config import get_logger


@dataclass
class LLMResponse:
    """Ответ от LLM"""
    text: str
    model: str
    processing_time: float
    tokens_used: Optional[int] = None
    confidence: Optional[float] = None


@dataclass
class LLMRequest:
    """Запрос к LLM"""
    prompt: str
    model: str
    temperature: float = 0.7
    max_tokens: Optional[int] = None
    system_prompt: Optional[str] = None
    context: Optional[Dict[str, Any]] = None


class OllamaService:
    """Сервис для работы с Ollama"""
    
    def __init__(self, config: OllamaConfig, logger=None):
        self.config = config
        self.logger = logger or get_logger("ollama")
        self._session = requests.Session()
        self._session.timeout = config.timeout
        
        # Статистика
        self._stats = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "total_processing_time": 0.0,
            "last_request_time": None,
            "connection_errors": 0
        }
        
        # Callback для уведомлений
        self._status_callback: Optional[Callable[[str], None]] = None
        
        self.logger.info(f"Ollama service initialized: {config.url}, model: {config.model}")
    
    def set_status_callback(self, callback: Callable[[str], None]):
        """Установить callback для уведомлений о статусе"""
        self._status_callback = callback
    
    def _notify_status(self, status: str):
        """Уведомить о изменении статуса"""
        if self._status_callback:
            try:
                self._status_callback(status)
            except Exception as e:
                self.logger.error(f"Status callback error: {e}")
    
    def _make_request(self, request: LLMRequest) -> Optional[LLMResponse]:
        """Выполнить запрос к Ollama"""
        start_time = time.time()
        
        try:
            # Формируем payload для Ollama
            payload = {
                "model": request.model,
                "prompt": request.prompt,
                "stream": False,
                "options": {}
            }
            
            if request.temperature is not None:
                payload["options"]["temperature"] = request.temperature
            
            if request.max_tokens is not None:
                payload["options"]["num_predict"] = request.max_tokens
            
            if request.system_prompt:
                payload["system"] = request.system_prompt
            
            self.logger.debug(f"Sending request to Ollama: {payload}")
            
            # Выполняем запрос
            response = self._session.post(
                self.config.url,
                json=payload,
                timeout=self.config.timeout
            )
            response.raise_for_status()
            
            # Парсим ответ
            data = response.json()
            response_text = data.get("response", "").strip()
            
            if not response_text:
                self.logger.warning("Empty response from Ollama")
                return None
            
            # Вычисляем время обработки
            processing_time = time.time() - start_time
            
            # Создаем результат
            result = LLMResponse(
                text=response_text,
                model=request.model,
                processing_time=processing_time,
                tokens_used=data.get("eval_count"),
                confidence=getattr(data, 'confidence', None)
            )
            
            # Обновляем статистику
            self._stats["total_requests"] += 1
            self._stats["successful_requests"] += 1
            self._stats["total_processing_time"] += processing_time
            self._stats["last_request_time"] = time.time()
            
            self.logger.info(f"Ollama request successful: {len(response_text)} chars, "
                           f"processing: {processing_time:.2f}s")
            
            return result
            
        except requests.exceptions.Timeout:
            self.logger.error("Ollama request timeout")
            self._stats["failed_requests"] += 1
            self._notify_status("timeout")
            return None
            
        except requests.exceptions.ConnectionError as e:
            self.logger.error(f"Ollama connection error: {e}")
            self._stats["connection_errors"] += 1
            self._stats["failed_requests"] += 1
            self._notify_status("connection_error")
            return None
            
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Ollama request error: {e}")
            self._stats["failed_requests"] += 1
            self._notify_status("request_error")
            return None
            
        except Exception as e:
            self.logger.error(f"Unexpected error in Ollama request: {e}")
            self._stats["failed_requests"] += 1
            self._notify_status("error")
            return None
    
    def process_text(self, text: str, task: str = "postprocess", 
                    custom_prompt: Optional[str] = None) -> Optional[LLMResponse]:
        """Обработать текст через LLM"""
        try:
            # Формируем промпт в зависимости от задачи
            if custom_prompt:
                prompt = custom_prompt
            elif task == "postprocess":
                prompt = (
                    "Ты редактор русского текста. Исправь пунктуацию, регистр, явные оговорки. "
                    "Сохраняй смысл, НЕ перефразируй лишнего. Удали междометия типа 'э-э', 'ну'. "
                    "Верни только финальный текст без пояснений.\n\nТекст:\n" + text
                )
            elif task == "summarize":
                prompt = (
                    "Сделай краткое резюме следующего текста на русском языке. "
                    "Сохрани ключевые моменты. Верни только резюме без пояснений.\n\nТекст:\n" + text
                )
            elif task == "translate":
                prompt = (
                    "Переведи следующий текст на английский язык. "
                    "Сохрани стиль и тон. Верни только перевод.\n\nТекст:\n" + text
                )
            else:
                prompt = text
            
            # Создаем запрос
            request = LLMRequest(
                prompt=prompt,
                model=self.config.model,
                temperature=0.1,  # Низкая температура для более предсказуемых результатов
                max_tokens=1000
            )
            
            return self._make_request(request)
            
        except Exception as e:
            self.logger.error(f"Failed to process text: {e}")
            return None
    
    def process_with_retry(self, text: str, task: str = "postprocess", 
                          max_retries: Optional[int] = None) -> Optional[LLMResponse]:
        """Обработать текст с повторными попытками"""
        if max_retries is None:
            max_retries = self.config.max_retries
        
        for attempt in range(max_retries + 1):
            try:
                result = self.process_text(text, task)
                if result is not None:
                    return result
                
                if attempt < max_retries:
                    self.logger.warning(f"LLM processing attempt {attempt + 1} failed, retrying...")
                    time.sleep(self.config.retry_delay)
                    
            except Exception as e:
                self.logger.error(f"LLM processing attempt {attempt + 1} error: {e}")
                if attempt < max_retries:
                    time.sleep(self.config.retry_delay)
        
        self.logger.error(f"All {max_retries + 1} LLM processing attempts failed")
        return None
    
    def test_connection(self) -> bool:
        """Проверить соединение с Ollama"""
        try:
            # Пробуем простой запрос
            test_request = LLMRequest(
                prompt="Привет",
                model=self.config.model,
                max_tokens=10
            )
            
            result = self._make_request(test_request)
            return result is not None
            
        except Exception as e:
            self.logger.error(f"Connection test failed: {e}")
            return False
    
    def get_available_models(self) -> List[str]:
        """Получить список доступных моделей"""
        try:
            # Используем API для получения списка моделей
            models_url = self.config.url.replace("/api/generate", "/api/tags")
            response = self._session.get(models_url, timeout=self.config.timeout)
            response.raise_for_status()
            
            data = response.json()
            models = [model["name"] for model in data.get("models", [])]
            
            self.logger.info(f"Available models: {models}")
            return models
            
        except Exception as e:
            self.logger.error(f"Failed to get available models: {e}")
            return []
    
    def change_model(self, model_name: str) -> bool:
        """Изменить модель"""
        try:
            old_model = self.config.model
            self.config.model = model_name
            
            # Проверяем доступность новой модели
            if self.test_connection():
                self.logger.info(f"Model changed from {old_model} to {model_name}")
                return True
            else:
                # Восстанавливаем старую модель
                self.config.model = old_model
                self.logger.error(f"Failed to change model to {model_name}")
                return False
                
        except Exception as e:
            self.logger.error(f"Failed to change model: {e}")
            return False
    
    def get_stats(self) -> Dict[str, Any]:
        """Получить статистику использования"""
        stats = self._stats.copy()
        if stats["total_requests"] > 0:
            stats["success_rate"] = stats["successful_requests"] / stats["total_requests"]
            stats["avg_processing_time"] = stats["total_processing_time"] / stats["successful_requests"]
        else:
            stats["success_rate"] = 0.0
            stats["avg_processing_time"] = 0.0
        
        return stats
    
    def clear_stats(self):
        """Очистить статистику"""
        self._stats = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "total_processing_time": 0.0,
            "last_request_time": None,
            "connection_errors": 0
        }
    
    def cleanup(self):
        """Очистка ресурсов"""
        try:
            if self._session:
                self._session.close()
            self.logger.info("Ollama service cleaned up")
        except Exception as e:
            self.logger.error(f"Cleanup error: {e}")
    
    def __del__(self):
        """Деструктор для автоматической очистки"""
        self.cleanup()


class LLMService:
    """Основной сервис для работы с LLM"""
    
    def __init__(self, config: OllamaConfig, logger=None):
        self.logger = logger or get_logger("llm")
        self.ollama_service = OllamaService(config, logger)
        
        # Fallback провайдеры (можно добавить другие)
        self._fallback_providers = []
        
        self.logger.info("LLM service initialized")
    
    def add_fallback_provider(self, provider_name: str, provider_func: Callable):
        """Добавить fallback провайдер"""
        self._fallback_providers.append((provider_name, provider_func))
        self.logger.info(f"Added fallback provider: {provider_name}")
    
    def process_text(self, text: str, task: str = "postprocess", 
                    use_fallback: bool = True) -> Optional[LLMResponse]:
        """Обработать текст через основной или fallback провайдеры"""
        # Пробуем основной сервис
        result = self.ollama_service.process_text(text, task)
        if result is not None:
            return result
        
        # Если не получилось и включены fallback
        if use_fallback and self._fallback_providers:
            for provider_name, provider_func in self._fallback_providers:
                try:
                    self.logger.info(f"Trying fallback provider: {provider_name}")
                    result = provider_func(text, task)
                    if result is not None:
                        self.logger.info(f"Fallback provider {provider_name} succeeded")
                        return result
                except Exception as e:
                    self.logger.error(f"Fallback provider {provider_name} failed: {e}")
        
        self.logger.warning("All LLM providers failed")
        return None
    
    def get_service_info(self) -> Dict[str, Any]:
        """Получить информацию о сервисе"""
        return {
            "main_provider": "ollama",
            "main_model": self.ollama_service.config.model,
            "fallback_providers": [name for name, _ in self._fallback_providers],
            "connection_status": self.ollama_service.test_connection()
        }
    
    def get_stats(self) -> Dict[str, Any]:
        """Получить статистику использования"""
        return self.ollama_service.get_stats()
    
    def cleanup(self):
        """Очистка ресурсов"""
        self.ollama_service.cleanup()
        self.logger.info("LLM service cleaned up")
    
    def __del__(self):
        """Деструктор для автоматической очистки"""
        self.cleanup()
