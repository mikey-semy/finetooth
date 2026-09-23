# Цели `make` для ревью. Вставляются в Makefile проекта как есть.
#
# Смысл целей — не сокращать набор символов, а убрать выбор: путь к инструменту
# и имена аргументов пишутся здесь один раз, и промпт нельзя собрать «немножко
# не так». Если в проекте нет Makefile, тот же список живёт в package.json,
# justfile или в чём угодно — см. package-json-snippet.json рядом.
#
# ⚠️ В присланном наборе на месте этого файла лежал фрагмент SAST-целей чужого
# проекта, и ни одна из команд `make review-*`, обещанных в документации, не
# существовала. Отсюда правило: команды, записанные в инструкции, выполняются
# при первой же установке, иначе инструкция описывает намерение, а не работу.

REVIEW := python3 .claude/skills/review-kit/scripts/review.py

.PHONY: review-init review-status review-next review-coverage review-check \
        review-prompt review-import review-findings

review-init: ## Создать state.json по blocks.json
	@$(REVIEW) init

review-status: ## Где мы: блоки по фазам, находки, следующий блок
	@$(REVIEW) status

review-next: ## id следующего незакрытого блока
	@$(REVIEW) next

review-coverage: ## Пересобрать карту «файл → блок»; падает, если файл ничей
	@$(REVIEW) coverage

review-check: ## Состояние непротиворечиво: статусы, отчёты, находки, покрытие
	@$(REVIEW) check

review-findings: ## Перегенерировать findings.md из findings.jsonl
	@$(REVIEW) findings

# Роль по умолчанию — охотник: с него начинается любой блок.
# make review-prompt BLOCK=H1 ROLE=verify
review-prompt: ## Собрать промпт агенту: BLOCK=H1 [ROLE=hunter|verify|fix]
	@test -n "$(BLOCK)" || { echo "укажите блок: make review-prompt BLOCK=H1"; exit 2; }
	@$(REVIEW) prompt $(BLOCK) --role $(or $(ROLE),hunter)

review-import: ## Втянуть находки блока в реестр: BLOCK=H1
	@test -n "$(BLOCK)" || { echo "укажите блок: make review-import BLOCK=H1"; exit 2; }
	@$(REVIEW) import $(BLOCK)
	@$(REVIEW) findings
	@$(REVIEW) check
