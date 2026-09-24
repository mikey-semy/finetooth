## What and why

<!-- which gap it closes or which defect it fixes; link to the issue -->

## Verification

- [ ] a test added or changed
- [ ] mutation: broke `…`, test `…` went red
- [ ] `python3 -m unittest discover -s tests` is green
- [ ] `skills-ref validate skills/finetooth` — Valid skill (if the skill was touched)
- [ ] entry in `CHANGELOG.md` ("Unreleased"); "Breaking" if the on-disk format changes
- [ ] the role prompt updated if a gate started requiring something new
- [ ] commits signed (`git commit -s`)
