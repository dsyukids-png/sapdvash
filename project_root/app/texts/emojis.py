class Emoji:
    def __init__(self, fallback: str, custom_id: str | None = None):
        self.fallback = fallback
        self.custom_id = custom_id

    def plain(self) -> str:
        """Возвращает обычный текст/эмодзи (используется для кнопок)."""
        return self.fallback

    def __str__(self):
        """Возвращает HTML-тег для сообщений или фолбек."""
        if self.custom_id:
            return f'<tg-emoji emoji-id="{self.custom_id}">{self.fallback}</tg-emoji>'
        return self.fallback

# ==========================================
# КОНФИГУРАЦИЯ PREMIUM ЭМОДЗИ
# ==========================================

class Emojis:
    # Главное меню
    MAIL = Emoji("✉️", custom_id="5967280668885913944")
    LINK = Emoji("🔗", custom_id="5877465816030515018")
    INBOX = Emoji("📦", custom_id="5924720918826848520")
    SETTINGS = Emoji("⚙️", custom_id="5877260593903177342")
    SUPPORT = Emoji("⭐️", custom_id="5958376256788502078")
    HELP = Emoji("ℹ️", custom_id="5956561749070057536")
    BOT = Emoji("🤖", custom_id="5872829476143894491")

    # Действия
    REPLY = Emoji("➡️", custom_id="5877468380125990242")
    BLOCK = Emoji("🚫", custom_id="5872829476143894491")
    REPORT = Emoji("⚠️", custom_id="5881702736843511327")
    BACK = Emoji("🔙", custom_id="5352759161945867747")
    SUCCESS = Emoji("✔️", custom_id="5825794181183836432")
    ERROR = Emoji("❌", custom_id="5778527486270770928")
    WARN = Emoji("❗️", custom_id="5879813604068298387")

    # Статусы и админка
    ADMIN = Emoji("🔨", custom_id="6028226658543082010")
    USER = Emoji("👤", custom_id="5879770735999717115")
    STATS = Emoji("📊", custom_id="5931472654660800739")
    LOGS = Emoji("🛠", custom_id="5988023995125993550")
    LOCK = Emoji("🔒", custom_id="5879895758202735862")
    UNLOCK = Emoji("🔓", custom_id="6034962180875490251")

    # Прочее
    SPAM = Emoji("🗑", custom_id="5879896690210639947")
    CLOCK = Emoji("🕒", custom_id="5778605968208170641")
    TICKET = Emoji("🔔", custom_id="5909201569898827582")