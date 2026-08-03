# ВГК Coal Dashboard — GitHub Pages + GitHub Actions

Дашборд публикуется через **GitHub Pages** (папка `/docs`), данные обновляются
автоматически через **GitHub Actions** (cron каждые 15 минут).

## Структура

```
docs/
  vgk-coal-scenario-live.html   ← сам дашборд (GitHub Pages)
  data/
    jkm.json                    ← авто: цена JKM с Investing.com
    risks.json                  ← авто: сгенерировано из risks_source.json
    risks_source.json           ← ВЫ РЕДАКТИРУЕТЕ ЭТОТ ФАЙЛ
scripts/
  update_dashboard_data.py      ← скрипт обновления
.github/workflows/
  update-data.yml               ← расписание запуска
```

## Настройка (один раз)

1. Settings → Pages → Source: **Deploy from a branch** → Branch `main`, Folder `/docs` → Save.
2. Settings → Actions → General → Workflow permissions → **Read and write permissions** → Save.
3. Вкладка Actions → включить workflows, если GitHub попросит.

## Проверка

Actions → «Update dashboard data» → **Run workflow** → через минуту проверить
`docs/data/jkm.json` — там должна быть свежая цена и `updated_at`.

## Как менять риски

Редактируйте только `docs/data/risks_source.json`. Поля:
`id`, `type` (`risk` | `upside`), `title`, `severity`
(`critical|high|medium|low|upside|fx_upside`), `impact`, `description`, `horizon`.

## Ограничения GitHub Actions

- Минимальный интервал cron — 5 минут, время в UTC.
- Возможны задержки запуска при высокой нагрузке.
- Scheduled workflow отключается после 60 дней без активности в репозитории.
