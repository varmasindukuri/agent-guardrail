import sys, hmac, hashlib, getpass, json, os

SCOPE = "scope.yaml"
SIG = "scope.sig"
AUTH = "secrets/auth.json"


def _hash_pw(pw, salt):
    return hashlib.scrypt(pw.encode(), salt=salt, n=2**14, r=8, p=1).hex()


def setup():
    os.makedirs("secrets", exist_ok=True)
    pw = getpass.getpass("Choose admin password: ")
    salt = os.urandom(16)
    key = os.urandom(32)
    json.dump({"salt": salt.hex(), "pw_hash": _hash_pw(pw, salt),
               "key": key.hex()}, open(AUTH, "w"))
    print("auth set up")


def _login():
    a = json.load(open(AUTH))
    pw = getpass.getpass("Admin password: ")
    if not hmac.compare_digest(_hash_pw(pw, bytes.fromhex(a["salt"])), a["pw_hash"]):
        print("wrong password")
        sys.exit(1)
    return bytes.fromhex(a["key"])


def sign():
    key = _login()
    data = open(SCOPE, "rb").read()
    open(SIG, "w").write(hmac.new(key, data, hashlib.sha256).hexdigest())
    print("scope signed")


def verify():
    a = json.load(open(AUTH))
    key = bytes.fromhex(a["key"])
    data = open(SCOPE, "rb").read()
    good = hmac.new(key, data, hashlib.sha256).hexdigest()
    ok = hmac.compare_digest(good, open(SIG).read().strip())
    print("scope OK" if ok else "SCOPE TAMPERED")
    return ok


if __name__ == "__main__":
    {"setup": setup, "sign": sign, "verify": verify}[sys.argv[1]]()