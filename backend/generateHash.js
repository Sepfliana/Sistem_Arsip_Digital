const bcrypt = require("bcrypt");

async function test() {

    const password = "admin123";

    const hash = await bcrypt.hash(password, 10);

    console.log(hash);

    const valid = await bcrypt.compare(
        password,
        hash
    );

    console.log(valid);

}

test();