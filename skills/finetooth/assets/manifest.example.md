# H1 — Authorization: RBAC, IDOR, data visibility

**Role:** security-authz · **Phase 1** · reports: `docs/review/reports/H1-authz.{hunter,verify}.md`

## Why this block is first

It is the only block where the cost of a mistake is the customer's data in the hands of
someone it is not meant for. The permission model in the project is layered: a gate on the
route, an ownership check in the usecase, a scope filter in the repository and, finally, a
grant in the seed. A defect can live in any layer, and it is visible only when looking at
all four at once.

If the project already has a **history of defects of this class** — name it here.
A typical example: grants that produce zero rows on a clean install, so a whole resource
is unavailable to every role except admin — and nobody notices for months, because in the
dev database the roles were created earlier. Such a line explains to the agent why the
block is first better than any general argument.

## What counts as a finding here

Any way to get access to an object or an action without the corresponding permission, and
also any discrepancy between the permission the code checks and the permission the seed
grants.

## Hypotheses

1. **A route without a gate.** Go through `router.go` in order and write out all the routes.
   Find those wrapped in neither `RequirePermission` nor `RequireAnyPermission`, and prove
   for each that it is deliberate (public `/auth/*`, health).
2. **A gate exists, ownership does not.** The permission `orders:read` opens reading orders —
   but a specific order? Find the handlers where, after the permission check, access to the
   object is not checked and the object is taken directly by id from the URL.
3. **An `*_own` permission without an ownership check.** `orders:update_own`, `attach_own`,
   `comment_own` make sense only together with comparing the object's owner with the
   actor (`order.OwnerID == actorID`). Check every such point.
4. **A scope that does not narrow.** Visibility by department, by role, by assignment: find
   the path where the filter is not applied — for example, a separate export endpoint, CSV
   export, a counter, search or a realtime event.
5. **Fail-open instead of fail-closed.** What happens when the scope could not be computed
   (the actor has no org unit, the directory is unavailable, the query returned an error)?
   An empty list is correct; a full list is a defect.
6. **A grant lost on a clean install.** For every migration that adds `permissions` or
   `role_permissions`, check that the corresponding resource/action pair is also in the
   roles seed (`db/seeds/001_roles_permissions.sql`). This is a mechanical comparison, and it
   must be done mechanically — write out the two lists and compare.
7. **A new read permission did not get into the `readonly` preset.**
8. **A permission is checked, but the wrong one.** A typo in the resource or action string
   gives a permission nobody has (silently breaks the function) or one everybody has.
   Compare the strings in the code with the permissions dictionary in the seed — both sides in full.
9. **The client decides instead of the server.** Find the places where an action is hidden
   only in the interface while the server endpoint is open wider. Especially if the project
   has several clients: branching by client type is a shell, not a permission.
10. **The system actor as a bypass.** Background jobs often run as a special system actor.
    Find the paths where it can be injected from a request.
11. **IDOR through a nested resource.** A comment, an attachment, a rating are fetched by
    their own id — is access to the PARENT order checked at the same time?
12. **The answer as an oracle.** Does the answer "no such object" differ from "the object
    exists but is not yours"? The second leaks the fact of existence; the project's
    convention is to return 404 in both cases.
13. **Permissions in realtime.** WS events and push notifications are addressed by recipient
    lists. Can a person receive an event about an order they have no right to see?
14. **A deactivated user.** A dismissed employee with a still-live token: where are
    `account_status` and `deleted_at` checked — on every request or only at login?

## Acceptance criterion

The report contains a **full route table** from `router.go` with the gate for each and a
mark about the ownership check, and also a **grant comparison table** migration↔seed.
Without these two tables the block is not closed.

## Special instructions

The live check of the permission matrix against the running API is done by block **E1**;
here — only reading the code. Everything worth checking live goes in a separate list at
the end of the report: it becomes the input for E1.
