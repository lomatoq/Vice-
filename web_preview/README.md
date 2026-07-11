# VAI Primitive Preview

Запуск из корня проекта:

```powershell
$python = 'C:\Users\nirrt\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
& $python .\web_preview\server.py --port 8877
```

Или одной командой с автоматическим открытием браузера:

```powershell
powershell -ExecutionPolicy Bypass -File .\Start-Preview.ps1
```

Открыть `http://127.0.0.1:8877`.

Возможности: несколько изображений, стабильный palette-экстрактор или Subpixel MiniNet 4×, восстановление скрытых цветовых слоёв, глобальное распознавание прямоугольников и эллипсов, CAD-регуляризация прямых, адаптивные кривые, залитый SVG, синхронный зум 25–800% и панорамирование. Vocabulary-квоты больше не используются.
