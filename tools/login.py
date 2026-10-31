"""Одноразовая авторизация аккаунта Telegram для точной проверки ников.

Запуск:  python3 tools/login.py

Два способа входа:
  1) QR-код (рекомендуется, не нужен код из SMS/чата): в терминале появится QR.
     На телефоне: Telegram → Настройки → Устройства → Подключить устройство → наведите камеру на QR.
  2) По номеру телефона и коду.

Лучше использовать отдельный (запасной) аккаунт. Сессия сохранится в data/user.session,
никому её не передавайте.
"""
import asyncio
import sys
from getpass import getpass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config  # noqa: E402


async def login_qr(client) -> bool:
    from telethon.errors import SessionPasswordNeededError

    try:
        import qrcode
    except ImportError:
        sys.exit("Установите библиотеку: pip install qrcode")

    qr = await client.qr_login()
    while True:
        print("\nОтсканируйте QR в Telegram на телефоне:")
        print("Настройки → Устройства → Подключить устройство\n")
        code = qrcode.QRCode(border=1)
        code.add_data(qr.url)
        code.make()
        code.print_ascii(invert=True)
        print(f"\nЕсли QR не читается, откройте на телефоне эту ссылку: {qr.url}\n")
        try:
            await qr.wait(timeout=55)
            return True
        except asyncio.TimeoutError:
            print("QR устарел, показываю новый...")
            await qr.recreate()
        except SessionPasswordNeededError:
            pwd = getpass("Пароль двухэтапной проверки: ")
            await client.sign_in(password=pwd)
            return True


async def login_code(client) -> None:
    from telethon.errors import PhoneCodeExpiredError, PhoneCodeInvalidError, SessionPasswordNeededError
    from telethon.tl.functions.auth import ResendCodeRequest

    phone = input("Номер телефона (в формате +7..., НЕ токен бота): ").strip()
    if ":" in phone:
        sys.exit("Это похоже на токен бота. Нужен номер телефона обычного аккаунта.")
    sent = await client.send_code_request(phone)
    kind = type(sent.type).__name__
    print(f"\nКод отправлен способом: {kind}")
    if "App" in kind:
        print("Откройте приложение Telegram: код (5 цифр) придёт в чат «Telegram».")
    print("Введите код. Не пришёл: sms, call или again.\n")
    while True:
        code = input("Код: ").strip().replace(" ", "")
        if code.lower() in ("sms", "call", "again"):
            try:
                sent = await client(ResendCodeRequest(phone, sent.phone_code_hash))
                print("Отправлено способом:", type(sent.type).__name__)
            except Exception as ex:
                print("Не удалось отправить повторно:", ex)
            continue
        try:
            await client.sign_in(phone, code, phone_code_hash=sent.phone_code_hash)
            return
        except SessionPasswordNeededError:
            await client.sign_in(password=getpass("Пароль двухэтапной проверки: "))
            return
        except PhoneCodeInvalidError:
            print("Неверный код (это 5 цифр), попробуйте ещё раз.")
        except PhoneCodeExpiredError:
            print("Код устарел. Введите again, чтобы получить новый.")


async def main() -> None:
    if not (config.TG_API_ID and config.TG_API_HASH):
        sys.exit("Заполните TG_API_ID и TG_API_HASH в .env")
    from telethon import TelegramClient

    config.DATA_DIR.mkdir(exist_ok=True)
    client = TelegramClient(config.TG_SESSION, config.TG_API_ID, config.TG_API_HASH,
                            connection_retries=8, retry_delay=2)
    try:
        await client.connect()
    except Exception as ex:
        sys.exit(f"Не удалось подключиться к Telegram ({ex!r}). Включите VPN и повторите.")

    if not await client.is_user_authorized():
        mode = input("Способ входа: 1 - QR-код (рекомендуется), 2 - номер и код [1]: ").strip() or "1"
        if mode == "2":
            await login_code(client)
        else:
            await login_qr(client)

    me = await client.get_me()
    if getattr(me, "bot", False):
        await client.log_out()
        sys.exit("Вошли как бот, а нужен обычный аккаунт. Запустите заново.")
    print(f"\nГотово, вошли как {me.first_name} (id {me.id}).")
    from telethon.sessions import StringSession
    string = StringSession.save(client.session)
    print("\nДля бота на ХОСТИНГЕ добавьте переменную окружения TG_SESSION_STRING со значением ниже.")
    print("Это полный доступ к аккаунту: никому не показывайте и не отправляйте в чат.\n")
    print(string)
    print("\nВажно: одну сессию нельзя использовать в двух местах сразу. Бот должен работать только на хостинге.")
    await client.disconnect()


asyncio.run(main())
