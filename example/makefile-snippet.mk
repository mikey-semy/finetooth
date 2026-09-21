    kind = t[0] if isinstance(t, list) and t else t
    # A rule that ran out of time on a file is not a file the parser could
    # not read: it is a loaded runner, and it comes and goes with the load.
    # Counted against the baseline it made the gate flap; it is reported on
    # its own line instead, so a persistent one still gets noticed.
    if kind in RESOURCE_ERRORS:
        timeouts[e.get('path')].append(e.get('rule_id') or kind)
        continue
    spans = t[1] if isinstance(t, list) and len(t) > 1 else []
    files[e.get('path')] = len(spans) if spans else 1
for p, rules in sorted(timeouts.items(), key=lambda kv: -len(kv[1])):
    names = ', '.join(r.rsplit('.', 1)[-1] for r in rules)
    if len(rules) >= TIMEOUT_THRESHOLD:
        # semgrep gave up on this file: the remaining rules never ran on it,
        # which is a file that was not read, whatever the parser thought.
        files[p] = max(files[p], 1)
        print('semgrep: %d rule(s) timed out on %s (%s) — scanning STOPPED on this file' % (len(rules), p, names))
    else:
        print('semgrep: %d rule(s) timed out on %s (%s) — raise --timeout if this repeats' % (len(rules), p, names))
if not files:
    print('semgrep: every file parsed in full'); raise SystemExit(0)
print('semgrep: %d file(s) only partially parsed — findings in the unread ranges are invisible:' % len(files))
for p, n in files.most_common():
    print('    %3d range(s)  %s' % (n, p))
if len(files) > limit:
    print('FAIL: %d files exceeds the baseline of %d. A new file stopped being read.' % (len(files), limit))
    raise SystemExit(1)
print('    (baseline %d, unchanged)' % limit)
endef
export SEMGREP_PARSE_PY

# shellcheck — the other half of IB plan F17. Nothing looked at the shell at
# all, and one of these scripts is db-init.sh, which creates the production
# administrator from ADMIN_EMAIL/ADMIN_PASSWORD and hashes it with pgcrypto.
# A quoting mistake there is not a style problem.
#
# .githooks is included because the pre-commit hook is what stops unformatted
# Go and un-hashed migrations from landing; a broken hook fails open.
SHELLCHECK_IMAGE ?= koalaman/shellcheck-alpine:v0.11.0
sast-shell: ## Static analysis of the shell scripts (shellcheck)
	@command -v shellcheck >/dev/null 2>&1 || { \
		echo "shellcheck not installed: pacman -S shellcheck / apt install shellcheck"; exit 1; }
	# infrastructure/deploy holds the one script that runs as root on the
	# deployment host, invoked by CI through a single sudo rule. It is the
	# whole of the boundary that replaced docker-group membership there, so
	# it is scanned on the same terms as db-init.sh. ci-disk-guard is here for
	# the same reason: it runs as root from a timer on a CI host and calls
	# docker prune, so a mistake in it deletes things nobody asked it to.
	shellcheck -f gcc infrastructure/docker/*.sh infrastructure/deploy/проект автора-deploy \
		infrastructure/gitlab-runner/ci-disk-guard .githooks/*
	@echo "shellcheck: clean"
