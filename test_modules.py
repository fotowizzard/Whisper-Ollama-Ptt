#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Тестирование основных модулей PTT приложения
"""

import sys
import traceback
from pathlib import Path

def test_config():
    """Тест модуля конфигурации"""
    print("🔧 Тестирование модуля конфигурации...")
    try:
        from config import CONFIG, AppConfig
        
        print(f"  ✓ Конфигурация загружена")
        print(f"  ✓ PTT клавиша: {CONFIG.ptt_key}")
        print(f"  ✓ Whisper модель: {CONFIG.whisper.model}")
        print(f"  ✓ Ollama модель: {CONFIG.ollama.model}")
        
        # Тест валидации
        if CONFIG.validate():
            print("  ✓ Конфигурация валидна")
        else:
            print("  ✗ Конфигурация невалидна")
        
        return True
        
    except Exception as e:
        print(f"  ✗ Ошибка: {e}")
        traceback.print_exc()
        return False

def test_logging():
    """Тест модуля логирования"""
    print("📝 Тестирование модуля логирования...")
    try:
        from logging_config import setup_logging, get_logger
        from config import CONFIG
        
        logger = setup_logging(CONFIG.logging)
        test_logger = get_logger("test")
        
        test_logger.info("Тестовое сообщение")
        test_logger.warning("Тестовое предупреждение")
        
        print("  ✓ Логирование настроено")
        print("  ✓ Логгеры работают")
        
        return True
        
    except Exception as e:
        print(f"  ✗ Ошибка: {e}")
        traceback.print_exc()
        return False

def test_audio_manager():
    """Тест модуля аудио менеджера"""
    print("🎵 Тестирование модуля аудио менеджера...")
    try:
        from audio_manager import AudioManager
        from config import CONFIG
        
        audio_manager = AudioManager(CONFIG.audio)
        
        # Тест получения устройств
        devices = audio_manager.get_available_devices()
        print(f"  ✓ Найдено аудио устройств: {len(devices)}")
        
        # Тест информации о буфере
        buffer_duration = audio_manager.get_buffer_duration()
        print(f"  ✓ Текущая длительность буфера: {buffer_duration:.2f}s")
        
        # Очистка
        audio_manager.cleanup()
        print("  ✓ Аудио менеджер протестирован")
        
        return True
        
    except Exception as e:
        print(f"  ✗ Ошибка: {e}")
        traceback.print_exc()
        return False

def test_whisper_service():
    """Тест модуля Whisper сервиса"""
    print("🤖 Тестирование модуля Whisper сервиса...")
    try:
        from transcription_service import WhisperService
        from config import CONFIG
        
        whisper_service = WhisperService(CONFIG.whisper)
        
        # Тест информации о модели
        model_info = whisper_service.get_model_info()
        print(f"  ✓ Статус модели: {model_info.get('status', 'unknown')}")
        
        # Тест статистики
        stats = whisper_service.get_stats()
        print(f"  ✓ Статистика: {stats['total_transcriptions']} транскрипций")
        
        # Очистка
        whisper_service.cleanup()
        print("  ✓ Whisper сервис протестирован")
        
        return True
        
    except Exception as e:
        print(f"  ✗ Ошибка: {e}")
        traceback.print_exc()
        return False

def test_llm_service():
    """Тест модуля LLM сервиса"""
    print("🧠 Тестирование модуля LLM сервиса...")
    try:
        from llm_service import LLMService
        from config import CONFIG
        
        llm_service = LLMService(CONFIG.ollama)
        
        # Тест информации о сервисе
        service_info = llm_service.get_service_info()
        print(f"  ✓ Основной провайдер: {service_info['main_provider']}")
        print(f"  ✓ Модель: {service_info['main_model']}")
        
        # Тест соединения
        connection_status = llm_service.ollama_service.test_connection()
        print(f"  ✓ Статус соединения: {'OK' if connection_status else 'FAILED'}")
        
        # Очистка
        llm_service.cleanup()
        print("  ✓ LLM сервис протестирован")
        
        return True
        
    except Exception as e:
        print(f"  ✗ Ошибка: {e}")
        traceback.print_exc()
        return False

def test_text_injection():
    """Тест модуля вставки текста"""
    print("📝 Тестирование модуля вставки текста...")
    try:
        from text_injection_service import TextInjectionService
        from config import CONFIG
        
        injection_service = TextInjectionService(CONFIG.text_injection)
        
        # Тест получения информации об активном окне
        window_info = injection_service._get_active_window_info()
        print(f"  ✓ Активное окно: {window_info['title']}")
        
        # Тест статистики
        stats = injection_service.get_stats()
        print(f"  ✓ Статистика вставок: {stats['total_injections']}")
        
        # Очистка
        injection_service.cleanup()
        print("  ✓ Сервис вставки текста протестирован")
        
        return True
        
    except Exception as e:
        print(f"  ✗ Ошибка: {e}")
        traceback.print_exc()
        return False

def test_tray_interface():
    """Тест модуля трей интерфейса"""
    print("🖥️ Тестирование модуля трей интерфейса...")
    try:
        from tray_interface import TrayIcon
        from config import CONFIG
        
        tray = TrayIcon(CONFIG)
        
        # Тест обновления статуса
        tray.set_status("ready")
        print("  ✓ Статус установлен")
        
        # Тест статистики
        test_stats = {"total_recordings": 5, "total_transcriptions": 3, "total_injections": 2}
        tray.update_stats(test_stats)
        print("  ✓ Статистика обновлена")
        
        # Очистка
        tray.cleanup()
        print("  ✓ Трей интерфейс протестирован")
        
        return True
        
    except Exception as e:
        print(f"  ✗ Ошибка: {e}")
        traceback.print_exc()
        return False

def main():
    """Основная функция тестирования"""
    print("🚀 Запуск тестирования модулей PTT приложения")
    print("=" * 50)
    
    tests = [
        test_config,
        test_logging,
        test_audio_manager,
        test_whisper_service,
        test_llm_service,
        test_text_injection,
        test_tray_interface
    ]
    
    results = []
    
    for test in tests:
        try:
            result = test()
            results.append(result)
            print()  # Пустая строка между тестами
        except Exception as e:
            print(f"  ✗ Критическая ошибка в тесте: {e}")
            results.append(False)
            print()
    
    # Итоговый отчет
    print("=" * 50)
    print("📊 ИТОГОВЫЙ ОТЧЕТ")
    print("=" * 50)
    
    passed = sum(results)
    total = len(results)
    
    print(f"✅ Успешно: {passed}/{total}")
    print(f"❌ Ошибок: {total - passed}/{total}")
    
    if passed == total:
        print("🎉 Все модули работают корректно!")
        return 0
    else:
        print("⚠️ Некоторые модули имеют проблемы")
        return 1

if __name__ == "__main__":
    try:
        exit_code = main()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n⏹️ Тестирование прервано пользователем")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 Критическая ошибка: {e}")
        traceback.print_exc()
        sys.exit(1)
