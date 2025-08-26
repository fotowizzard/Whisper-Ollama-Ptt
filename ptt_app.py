#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Основное приложение PTT
"""

import os
import sys
import time
import threading
import traceback
from typing import Optional, Dict, Any
from config import AppConfig, CONFIG
from logging_config import setup_logging, get_logger
from audio_manager import AudioManager
from transcription_service import WhisperService
from llm_service import LLMService
from text_injection_service import TextInjectionService
from tray_interface import TrayIcon


class PTTApp:
    """Основное приложение Push-to-Talk"""
    
    def __init__(self, config: AppConfig):
        self.config = config
        self.logger = get_logger("main")
        
        # Инициализируем сервисы
        self.audio_manager: Optional[AudioManager] = None
        self.whisper_service: Optional[WhisperService] = None
        self.llm_service: Optional[LLMService] = None
        self.text_injection_service: Optional[TextInjectionService] = None
        self.tray_interface: Optional[TrayIcon] = None
        
        # Состояние приложения
        self._running = False
        self._recording = False
        self._processing = False
        
        # Статистика
        self._stats = {
            "total_recordings": 0,
            "total_transcriptions": 0,
            "total_injections": 0,
            "total_errors": 0,
            "start_time": time.time()
        }
        
        # Блокировки
        self._processing_lock = threading.Lock()
        
        self.logger.info("PTT application initializing...")
        self._initialize_services()
        self._setup_callbacks()
    
    def _initialize_services(self):
        """Инициализация всех сервисов"""
        try:
            # Инициализируем аудио менеджер
            self.logger.info("Initializing audio manager...")
            self.audio_manager = AudioManager(self.config.audio, get_logger("audio"))
            self.audio_manager.set_status_callback(self._on_audio_status)
            
            # Инициализируем сервис транскрипции
            self.logger.info("Initializing Whisper service...")
            self.whisper_service = WhisperService(self.config.whisper, get_logger("whisper"))
            
            # Инициализируем LLM сервис
            self.logger.info("Initializing LLM service...")
            self.llm_service = LLMService(self.config.ollama, get_logger("llm"))
            
            # Инициализируем сервис вставки текста
            self.logger.info("Initializing text injection service...")
            self.text_injection_service = TextInjectionService(
                self.config.text_injection, 
                get_logger("text_injection")
            )
            self.text_injection_service.set_status_callback(self._on_injection_status)
            
            # Инициализируем трей интерфейс
            self.logger.info("Initializing tray interface...")
            self.tray_interface = TrayIcon(self.config, get_logger("tray"))
            self._setup_tray_callbacks()
            
            self.logger.info("All services initialized successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize services: {e}")
            raise
    
    def _setup_callbacks(self):
        """Настройка callback'ов между сервисами"""
        try:
            # Аудио менеджер -> основной поток
            if self.audio_manager:
                self.audio_manager.set_status_callback(self._on_audio_status)
            
            # Сервис вставки -> основной поток
            if self.text_injection_service:
                self.text_injection_service.set_status_callback(self._on_injection_status)
            
            self.logger.debug("Callbacks setup completed")
            
        except Exception as e:
            self.logger.error(f"Failed to setup callbacks: {e}")
    
    def _setup_tray_callbacks(self):
        """Настройка callback'ов для трей интерфейса"""
        try:
            if not self.tray_interface:
                return
            
            # Регистрируем callback'и для статуса
            self.tray_interface.register_status_callback("autopaste_toggle", self._on_autopaste_toggle)
            
            # Регистрируем callback'и для меню
            self.tray_interface.register_menu_callback("test_injection", self._test_injection)
            self.tray_interface.register_menu_callback("test_audio", self._test_audio)
            self.tray_interface.register_menu_callback("show_settings", self._show_settings)
            self.tray_interface.register_menu_callback("show_about", self._show_about)
            self.tray_interface.register_menu_callback("exit", self._on_exit)
            
            self.logger.debug("Tray callbacks setup completed")
            
        except Exception as e:
            self.logger.error(f"Failed to setup tray callbacks: {e}")
    
    def _on_audio_status(self, status: str):
        """Обработка изменения статуса аудио"""
        try:
            self.logger.debug(f"Audio status: {status}")
            
            if status == "recording":
                self._recording = True
                self._processing = False
            elif status == "processing":
                self._recording = False
                self._processing = True
            elif status in ["ready", "no_audio", "error"]:
                self._recording = False
                self._processing = False
            
            # Обновляем трей интерфейс
            if self.tray_interface:
                self.tray_interface.set_status(status)
            
        except Exception as e:
            self.logger.error(f"Audio status callback error: {e}")
    
    def _on_injection_status(self, status: str):
        """Обработка изменения статуса вставки"""
        try:
            self.logger.debug(f"Injection status: {status}")
            
            if status == "injected":
                self._stats["total_injections"] += 1
                self._update_stats()
            
        except Exception as e:
            self.logger.error(f"Injection status callback error: {e}")
    
    def _on_autopaste_toggle(self, enabled: bool):
        """Обработка переключения авто-вставки"""
        try:
            self.logger.info(f"Autopaste toggled to: {enabled}")
            
            # Обновляем конфигурацию
            self.config.text_injection.autopaste = enabled
            
            # Уведомляем пользователя
            if self.tray_interface:
                status = "ВКЛ" if enabled else "ВЫКЛ"
                self.tray_interface.show_notification(
                    "Авто-вставка",
                    f"Автоматическая вставка текста {status}",
                    3
                )
            
        except Exception as e:
            self.logger.error(f"Autopaste toggle callback error: {e}")
    
    def _test_injection(self):
        """Тест вставки текста"""
        try:
            self.logger.info("Testing text injection...")
            
            test_text = "Тест вставки текста - " + time.strftime("%H:%M:%S")
            
            if self.text_injection_service:
                result = self.text_injection_service.inject_text(test_text, force_method="typing")
                
                if result.success:
                    self.tray_interface.show_notification(
                        "Тест вставки",
                        "Вставка текста прошла успешно",
                        3
                    )
                else:
                    self.tray_interface.show_notification(
                        "Тест вставки",
                        f"Ошибка вставки: {result.error_message}",
                        5
                    )
            
        except Exception as e:
            self.logger.error(f"Test injection failed: {e}")
            if self.tray_interface:
                self.tray_interface.show_notification(
                    "Тест вставки",
                    f"Ошибка: {str(e)}",
                    5
                )
    
    def _test_audio(self):
        """Тест аудио"""
        try:
            self.logger.info("Testing audio...")
            
            if self.audio_manager:
                # Проверяем доступные устройства
                devices = self.audio_manager.get_available_devices()
                
                if devices:
                    device_info = f"Найдено устройств: {len(devices)}"
                    for device in devices[:3]:  # Показываем первые 3
                        device_info += f"\n- {device['name']}"
                    
                    self.tray_interface.show_notification(
                        "Тест аудио",
                        device_info,
                        5
                    )
                else:
                    self.tray_interface.show_notification(
                        "Тест аудио",
                        "Аудио устройства не найдены",
                        5
                    )
            
        except Exception as e:
            self.logger.error(f"Test audio failed: {e}")
            if self.tray_interface:
                self.tray_interface.show_notification(
                    "Тест аудио",
                    f"Ошибка: {str(e)}",
                    5
                )
    
    def _show_settings(self):
        """Показать настройки"""
        try:
            self.logger.info("Showing settings...")
            
            # Краткое уведомление для трея (ограничение 64 символа)
            short_settings = f"PTT: {self.config.ptt_key.upper()}, Whisper: {self.config.whisper.model}"
            
            # Полная информация для лога
            full_settings = f"""
Основные настройки:
• Клавиша PTT: {self.config.ptt_key.upper()}
• Модель Whisper: {self.config.whisper.model}
• Модель LLM: {self.config.ollama.model}
• Авто-вставка: {'ВКЛ' if self.config.text_injection.autopaste else 'ВЫКЛ'}
• Частота дискретизации: {self.config.audio.sample_rate}Hz
            """.strip()
            
            # Логируем полную информацию
            self.logger.info(f"Current settings: {full_settings}")
            
            # Показываем краткое уведомление в трее
            if self.tray_interface:
                self.tray_interface.show_notification(
                    "Настройки",
                    short_settings,
                    8
                )
            
        except Exception as e:
            self.logger.error(f"Show settings failed: {e}")
    
    def _show_about(self):
        """Показать информацию о программе"""
        try:
            self.logger.info("Showing about...")
            
            # Информация уже формируется в трей интерфейсе
            # Здесь можно добавить дополнительную логику
            
        except Exception as e:
            self.logger.error(f"Show about failed: {e}")
    
    def _on_exit(self):
        """Обработка выхода"""
        try:
            self.logger.info("Exit requested")
            self.stop()
            
        except Exception as e:
            self.logger.error(f"Exit failed: {e}")
            import os
            os._exit(1)
    
    def _update_stats(self):
        """Обновить статистику"""
        try:
            # Обновляем статистику в трее
            if self.tray_interface:
                self.tray_interface.update_stats(self._stats)
            
            self.logger.debug("Stats updated")
            
        except Exception as e:
            self.logger.error(f"Failed to update stats: {e}")
    
    def start_recording(self):
        """Начать запись"""
        if self._recording or self._processing:
            self.logger.warning("Recording or processing already in progress")
            return
        
        try:
            if self.audio_manager:
                success = self.audio_manager.start_recording()
                if success:
                    self._stats["total_recordings"] += 1
                    self._update_stats()
                    self.logger.info("Recording started")
                else:
                    self.logger.error("Failed to start recording")
            
        except Exception as e:
            self.logger.error(f"Start recording failed: {e}")
            self._stats["total_errors"] += 1
    
    def stop_recording(self):
        """Остановить запись"""
        if not self._recording:
            self.logger.warning("No recording in progress")
            return
        
        try:
            if self.audio_manager:
                audio = self.audio_manager.stop_recording()
                if audio is not None:
                    # Запускаем обработку в отдельном потоке
                    threading.Thread(
                        target=self._process_audio,
                        args=(audio,),
                        daemon=True
                    ).start()
                else:
                    self.logger.warning("No audio recorded")
            
        except Exception as e:
            self.logger.error(f"Stop recording failed: {e}")
            self._stats["total_errors"] += 1
    
    def _process_audio(self, audio):
        """Обработка записанного аудио"""
        if not self._processing_lock.acquire(blocking=False):
            self.logger.warning("Another processing in progress, skipping")
            return
        
        try:
            self._processing = True
            self.logger.info("Processing audio...")
            
            # Обновляем статус
            if self.tray_interface:
                self.tray_interface.set_status("processing")
            
            # 1. Транскрипция через Whisper
            if self.whisper_service:
                transcription_result = self.whisper_service.transcribe_with_retry(audio)
                
                if transcription_result:
                    self._stats["total_transcriptions"] += 1
                    self.logger.info(f"Transcription: {transcription_result.text}")
                    
                    # 2. Пост-обработка через LLM
                    if self.llm_service:
                        llm_result = self.llm_service.process_text(
                            transcription_result.text,
                            task="postprocess"
                        )
                        
                        if llm_result:
                            final_text = llm_result.text
                            self.logger.info(f"LLM processing: {final_text}")
                        else:
                            final_text = transcription_result.text
                            self.logger.warning("LLM processing failed, using raw transcription")
                    else:
                        final_text = transcription_result.text
                    
                    # 3. Вставка текста
                    if self.config.text_injection.autopaste and self.text_injection_service:
                        injection_result = self.text_injection_service.inject_text(final_text)
                        
                        if injection_result.success:
                            self.logger.info("Text injected successfully")
                        else:
                            self.logger.error(f"Text injection failed: {injection_result.error_message}")
                            # Копируем в буфер обмена как fallback
                            self.text_injection_service.copy_to_clipboard(final_text)
                    else:
                        # Просто копируем в буфер обмена
                        if self.text_injection_service:
                            self.text_injection_service.copy_to_clipboard(final_text)
                            self.logger.info("Text copied to clipboard")
                    
                    # Обновляем статистику
                    self._update_stats()
                    
                else:
                    self.logger.error("Transcription failed")
                    if self.tray_interface:
                        self.tray_interface.show_notification(
                            "Ошибка",
                            "Не удалось распознать речь",
                            5
                        )
            
        except Exception as e:
            self.logger.error(f"Audio processing failed: {e}")
            self._stats["total_errors"] += 1
            
            if self.tray_interface:
                self.tray_interface.show_notification(
                    "Ошибка",
                    f"Ошибка обработки: {str(e)}",
                    5
                )
        
        finally:
            self._processing = False
            self._processing_lock.release()
            
            # Обновляем статус
            if self.tray_interface:
                self.tray_interface.set_status("ready")
    
    def run(self):
        """Запуск основного цикла приложения"""
        try:
            self._running = True
            self.logger.info(f"PTT application started. Hold {self.config.ptt_key.upper()} to speak.")
            
            # Импортируем keyboard здесь для избежания проблем с импортом
            import keyboard
            
            # Регистрируем горячие клавиши
            keyboard.on_press_key(self.config.ptt_key, lambda e: self.start_recording())
            keyboard.on_release_key(self.config.ptt_key, lambda e: self.stop_recording())
            
            # Основной цикл
            while self._running:
                time.sleep(0.1)  # Небольшая пауза для снижения нагрузки на CPU
                
                # Обновляем статистику каждые 5 секунд
                if int(time.time()) % 5 == 0:
                    self._update_stats()
            
        except KeyboardInterrupt:
            self.logger.info("Keyboard interrupt received")
        except Exception as e:
            self.logger.error(f"Main loop error: {e}")
            traceback.print_exc()
        finally:
            self.stop()
    
    def stop(self):
        """Остановка приложения"""
        try:
            self.logger.info("Stopping PTT application...")
            self._running = False
            
            # Останавливаем запись если идет
            if self._recording and self.audio_manager:
                self.audio_manager.stop_recording()
            
            # Очищаем ресурсы
            self._cleanup_services()
            
            self.logger.info("PTT application stopped")
            
        except Exception as e:
            self.logger.error(f"Stop failed: {e}")
    
    def _cleanup_services(self):
        """Очистка всех сервисов"""
        try:
            # Очищаем сервисы в обратном порядке
            if self.tray_interface:
                self.tray_interface.cleanup()
                self.tray_interface = None
            
            if self.text_injection_service:
                self.text_injection_service.cleanup()
                self.text_injection_service = None
            
            if self.llm_service:
                self.llm_service.cleanup()
                self.llm_service = None
            
            if self.whisper_service:
                self.whisper_service.cleanup()
                self.whisper_service = None
            
            if self.audio_manager:
                self.audio_manager.cleanup()
                self.audio_manager = None
            
            self.logger.info("All services cleaned up")
            
        except Exception as e:
            self.logger.error(f"Service cleanup failed: {e}")
    
    def __del__(self):
        """Деструктор для автоматической очистки"""
        self.stop()


def main():
    """Главная функция"""
    try:
        # Настраиваем логирование
        logger = setup_logging(CONFIG.logging)
        logger.info("PTT application starting...")
        
        # Создаем и запускаем приложение
        app = PTTApp(CONFIG)
        app.run()
        
    except Exception as e:
        # Логируем критическую ошибку
        if 'logger' in locals():
            logger.critical(f"Fatal error: {e}")
            logger.critical(traceback.format_exc())
        else:
            print(f"Fatal error: {e}")
            traceback.print_exc()
        raise


if __name__ == "__main__":
    main()
