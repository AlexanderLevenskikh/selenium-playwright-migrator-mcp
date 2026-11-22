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


## Публичный NUnit-проект и доказательства MCP (draft #64, 22.11.2026)

Новая stdio-проверка на Linux и Windows с точным Core pin сообщает
агенту только SHA и эффекты исходного `SampleAppPage.Login`:
ввод username/password, Click, отдельное чтение текста.
Неизвестные или динамические `By.Name`, alias и устаревший
`SourceTreeHash` блокируются. Сырые селекторы и исполняемый C#
**не раскрываются** через MCP.

Оригинальный полный NUnit-проект
`desh2001/Selenium-NUnit-Automation@edacb9feb41a7e21d9b6bf6924f24c11698a4427`
успешно собрался и обнаружил 10 тестов; настоящий Core создал
**полный target Playwright NUnit проект** (четыре C# файла, `.csproj`,
manifest): на Linux/Windows сборка и discovery **10/10 PASS**.
Но полный исходный/целевой NUnit **не запускался**.
`acceptance-inspect` обнаружил **125 source obligations / 115
пропущенных** и вернул `rejected_incomplete`. На target остаются
TODO по POM, DriverManager, NUnit lifecycle и assertions.
Реальный Chromium Selenium→Core POM oracle доказывает только
отдельные методы Login/Message/навигации, не полный fixture.

Для workflow агента `rejected_incomplete` и `UNKNOWN` —
обязательные блокеры: никакого autoapply, запуска чужого кода или
подтверждения эквивалентности по зелёному NUnit/discovery. Два
других публичных проекта пока только read-only source evidence.
P1 #59 OPEN, NO FIX CLAIM, релиз/merge запрещены.
См. [подробности MCP](docs/P2-P3-CORE-PROJECTED-CONSUMER.md)
и [RC #80](https://github.com/levencode-labs/selenium-playwright-migrator-core/issues/80).
