from pydantic import BaseModel, ConfigDict


class RegisterBody(BaseModel):
    username: str
    password: str
    invite_code: str = ""


class LoginBody(BaseModel):
    username: str
    password: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    is_admin: bool


class AuthResult(BaseModel):
    token: str
    user: UserOut


class PasswordChange(BaseModel):
    old_password: str
    new_password: str


class VersionInfo(BaseModel):
    build: int
    note: str
    apk_sha256: str = ""
