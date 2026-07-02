You are an expert C++ developer for InjectorGPN.
  - NEVER read the same file twice in one conversation unless explicitly asked.
  - NEVER re-read CLAUDE.md after the first turn.
  - NEVER output file content. Introduce changes directly into the file so they are seen in Source Control
  - If unsure about a file's content, ask a concise yes/no question instead of reading it.

InjectorGPN — C++20, Eigen, Catch2, nlohmann_json, OpenMP
Пространство имён: GPN

Структура (ключевые модули)
Grids/ – 1D/2D сетки, индексация to_linear(row,col)
Model/Collector/ – коллекторы (газ/жидкость)
Model/Heat/ – TemperatureField, HeatSolver, JT
Model/Hydrodynamic/ – сжимаемые/несжимаемые флюиды
Model/Phases/ – свойства флюидов
Solver/FullImplicit/ – FullImplicitSolver (температура + давление)
Solver/SplittingMethod/ – расщепление
Properties/ – Logs, FlowField, FaceProperties, JT_FieldFactory

Ключевые классы и паттерны
GridNodeValues2D = Eigen::ArrayXXd (размер nz×nr)
FaceValuesContainer – значения на гранях
FullImplicitSolver::advance(tau) – собирает матрицу, RHS, решает
Джоуль–Томсон: JT_FieldFactory (create_spatial, create_temporal). EmptyJT – заглушка для PointGas. Выбор через std::conditional_t
Фабрики: *Factory → cptr<T> = std::shared_ptr<const T>
Граничные условия температуры: West (скважина: I или II рода), East (геотерма), South (устье), North (забой) – поток * T_inlet

Соглашения
Только заголовочные файлы (.hpp), реализация в шаблонах
Входные параметры: const &, хранение фабрик: cptr<T>
Конструкторы: move default, copy delete (если есть GridNodeValues2D)
dynamic_cast не используется
use clean design

Тесты группируются #pragma region

Инструкции для Claude Code
Отвечай кратко, без лирических отступлений.
Если просят код — давай только изменённые фрагменты с ... для неизменённых частей.
Предпочитай существующие паттерны (фабрики, cptr, assert).
Не пиши пояснения к очевидным конструкциям.
При тестах копируй структуру #pragma region из существующих файлов.

Автономный режим
- Собирай и запускай тесты без запроса разрешения
- Коммить изменения без согласования сообщения, используя формат: `<тип>: <краткое описание>`
- В сообщениях коммитах не упоминай себя
- При ошибке сборки — исправляй и пересобирай автоматически

Режим редактирования
- Вноси изменения в файлы напрямую, без вывода диффов в чат
- Не показывай предварительный просмотр изменений — сразу редактируй файл
- Не спрашивай подтверждения перед записью в файл

Рабочие директории
Разрешено переходить в любые поддиректории репозитория без подтверждения.

Obsidian Knowledge Vault
Хранилище знаний: d:\Lessons\Grants\2025\GPN\Vault\InjectorGPN\

При старте сессии
Прочитай 00-home/index.md и текущие приоритеты.md.
Если задача касается модуля — прочитай заметку из knowledge/.

При завершении (пользователь: "сохрани сессию")
1. Создай заметку в sessions/ с датой
2. Обнови текущие приоритеты.md
3. Если решение — создай в knowledge/decisions/
4. Если баг — создай в knowledge/debugging