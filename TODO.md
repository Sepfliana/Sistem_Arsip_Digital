# TODO - Fix bcrypt redeclaration in UserController

- [ ] Inspect `backend/controllers/UserController.js` to confirm where `bcrypt` is declared twice.
- [ ] Update `backend/controllers/UserController.js` to remove the duplicate `const bcrypt = require("bcrypt");` so Node can compile.
- [ ] Restart backend (or rely on nodemon) and verify server starts without SyntaxError.

