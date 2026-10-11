from pydantic import BaseModel


class ChatQuizOption(BaseModel):
    key: str
    html: str


class ChatQuiz(BaseModel):
    qid: str
    system: str
    multi: bool
    stem_html: str
    options: list[ChatQuizOption]


class ChatMessageOut(BaseModel):
    role: str
    content: str
    html: str
    created_at: str


class ChatReply(BaseModel):
    reply: str
    reply_html: str
    quizzes: list[ChatQuiz]


class ChatFile(BaseModel):
    name: str = "file"
    data: str = ""


class ChatSendBody(BaseModel):
    message: str = ""
    context: str | None = None
    image: str | None = None
    file: ChatFile | None = None


class ChatAnswerBody(BaseModel):
    qid: str
    answer: str


class ChatAnswerResult(BaseModel):
    correct: bool
    answer: str
    qid: str
    reply: str
    reply_html: str
