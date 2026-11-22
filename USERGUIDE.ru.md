# Selenium → Playwright Migrator MCP — руководство (подготовка RC)

**Статус: предварительная версия, production NO-GO.** MCP-сервер работает по stdio и предоставляет консервативный read-only анализ, preview и проверку точной версии результата. Автоматическое применение изменений и доказанная общая эквивалентность Selenium→Playwright отсутствуют. Windows Chromium orphan [Core #59](https://github.com/levencode-labs/selenium-playwright-migrator-core/issues/59) остаётся открытым.

## Работа через MCP

Для `MIGRATOR_WORKSPACE` задайте абсолютный путь к существующему доверенному проекту. Пути инструментов — относительно workspace; рекурсивные symlink/reparse points отклоняются. Это не полноценная ОС-песочница.

1. `analyze_migration` — инвентаризация NUnit/POM и блокеров, сохраните `analysisId` и `sourceTreeHash`.
2. `preview_migration` с точным `expectedAnalysisId` — генерация консервативного кандидата и `candidateId` (без изменения исходников).
3. После ревью редактируйте целевые C# файлы **вне MCP** в отдельной папке.
4. `verify_artifact` с точными analysis/parent candidate и `targetRoot` — проверка хешей, нового `CandidateId`, обязательного `migrator-acceptance/v1`, стадий syntax/compile/testDiscovery/runner/realBrowser/behavioralEquivalence.
5. `rejected_incomplete` — потеряно обязательное действие/assertion/helper/fixture/путь отказа; миграцию **остановить**. `blocked_unverified` или `candidate_unverified` — не доказана эквивалентность. `not_run` не означает PASS.

`runCompile=true` выполняет только in-memory Roslyn compile с явным `referenceDlls`, а не полноценный project build, NUnit или браузер. MCP не запускает чужой код автоматически.

## Сборка и проверки

Точный Core SHA закреплён в **двух** checkout шагах `.github/workflows/mcp-ci.yml`. CI собирает локальный NuGet feed, проверяет Linux MCP stdio и автономный Windows x64 пакет. До публикации официального релиза не используйте старые инструкции о публичных NuGet версиях как подтверждённую установку.

Интеграционные stdio-регрессии отклоняют потерянный `SetUpFixture`, унаследованную базу NUnit и private-helper Click. Core независимо проверяет браузерные Selenium↔Playwright события и два негативных сценария. Три внешних публичных проекта исследованы только по исходникам — их behavioral equivalence **UNKNOWN**.

**До доказанного исправления Core #59, независимой приёмки реальных проектов и полной 28+2 CI выпуск запрещён.** Main, исходный P47, SIGTERM, 12-секундный gate и исторические FAIL не изменяются.
