import { canRead } from "../src/auth/guard";
test("owner reads own", () => expect(canRead("u1:user", "u1")).toBe(true));
