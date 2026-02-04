import logging
import re
import time
from telegram import Update, ChatPermissions
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters
from config import *
from database import db


logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO if not DEBUG else logging.DEBUG
)

def is_emoji_only(text: str) -> bool:
    if not text: return False
    cleaned = re.sub(r'\s', '', text)
    if not cleaned: return False
    emoji_pattern = re.compile(
        "[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF"
        "\U0001F1E0-\U0001F1FF\U00002702-\U000027B0\U000024C2-\U0001F251]+",
        flags=re.UNICODE)
    return bool(emoji_pattern.fullmatch(cleaned))

def can_mute_user(muter_id: int, target_id: int) -> bool:
    if target_id in SENIOR_ADMIN_IDS:
        return False
    return db.get_user_level(muter_id) > db.get_user_level(target_id)

def can_change_level(changer_id: int, target_id: int, new_level: int) -> tuple:
    if target_id in SENIOR_ADMIN_IDS and changer_id != target_id:
        return False, "Нельзя менять уровень старших админов"
    
    changer_level = db.get_user_level(changer_id)
    target_level = db.get_user_level(target_id)
    
    if changer_level <= target_level and changer_id != target_id:
        return False, "У вас недостаточно прав"
    
    if new_level >= changer_level and changer_id != target_id:
        return False, "Нельзя установить уровень выше или равный своему"
    
    if new_level > 6:
        return False, "Максимальный уровень - 6"
    
    return True, ""

async def update_chat_owner_level(chat_id: int, bot):
    try:
        chat_admins = await bot.get_chat_administrators(chat_id)
        for admin in chat_admins:
            if admin.status == 'creator':
                owner_id = admin.user.id
                if owner_id not in SENIOR_ADMIN_IDS:
                    SENIOR_ADMIN_IDS.append(owner_id)
                db.set_user_level(
                    owner_id, 
                    6, 
                    admin.user.username,
                    admin.user.first_name
                )
                return owner_id
    except Exception as e:
        if DEBUG:
            print(f"Ошибка обновления владельца: {e}")
    return None

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    user = update.effective_user
    
    await update_chat_owner_level(chat_id, context.bot)
    
    db.set_user_level(
        user_id,
        db.get_user_level(user_id),
        user.username,
        user.first_name
    )
    
    level = db.get_user_level(user_id)
    await update.message.reply_text(
        f"🤖 Бот-модератор с уровнями!\n"
        f"Ваш уровень: {LEVELS[level]}\n"
        f"Используйте /help для списка команд"
    )

async def mylevel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    user = update.effective_user
    
    await update_chat_owner_level(chat_id, context.bot)
    
    db.set_user_level(
        user_id,
        db.get_user_level(user_id),
        user.username,
        user.first_name
    )
    
    level = db.get_user_level(user_id)
    stats = db.get_user_stats(user_id)
    
    if level == 6:
        message = f"👑 Вы - Старший админ!\nID: {user_id}\n"
    else:
        message = f"📊 Ваш уровень: {LEVELS[level]}\nID: {user_id}\n"
    
    message += f"📨 Сообщений: {stats['total_messages']}\n"
    message += f"🎨 Стикеров: {stats['total_stickers']}\n"
    message += f"⚠️ Муты: {stats['total_mutes']}"
    
    await update.message.reply_text(message)

async def list_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    
    try:
        await update_chat_owner_level(chat_id, context.bot)
        
        level_users = {level: [] for level in range(6, 0, -1)}
        
        all_users = db.get_all_users()
        user_ids_in_chat = set()
        
        async for member in context.bot.get_chat_members(chat_id):
            user_ids_in_chat.add(member.user.id)
            db.set_user_level(
                member.user.id,
                db.get_user_level(member.user.id),
                member.user.username,
                member.user.first_name
            )
        
        for user_data in all_users:
            if user_data['user_id'] in user_ids_in_chat:
                level = user_data['level']
                username = f"@{user_data['username']}" if user_data['username'] else user_data['first_name'] or f"ID: {user_data['user_id']}"
                level_users[level].append(username)
        
        message_lines = ["📋 Пользователи по уровням:\n"]
        
        for level in range(6, 0, -1):
            users_list = level_users[level]
            if users_list:
                users = ", ".join(users_list[:15])
                if len(users_list) > 15:
                    users += f" и еще {len(users_list) - 15}"
                
                message_lines.append(f"\n{LEVELS[level]} ({len(users_list)}):\n{users}")
        
        if len(message_lines) == 1:
            await update.message.reply_text("📭 В чате пока нет пользователей с уровнями")
        else:
            await update.message.reply_text("".join(message_lines))
            
    except Exception as e:
        if DEBUG:
            print(f"Ошибка в /list: {e}")
        await update.message.reply_text("❌ Ошибка получения списка")

async def setlevel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    
    if db.get_user_level(user_id) < 5:
        await update.message.reply_text("❌ Только админы могут использовать эту команду!")
        return
    
    if not context.args or len(context.args) != 2:
        await update.message.reply_text("❌ Формат: /setlevel @username уровень")
        return
    
    username = context.args[0].lstrip('@')
    try:
        new_level = int(context.args[1])
    except ValueError:
        await update.message.reply_text("❌ Уровень должен быть числом от 1 до 6")
        return
    
    if new_level < 1 or new_level > 6:
        await update.message.reply_text("❌ Уровень должен быть от 1 до 6")
        return
    
    target_user = None
    try:
        async for member in context.bot.get_chat_members(chat_id):
            if member.user.username and member.user.username.lower() == username.lower():
                target_user = member.user
                break
    except Exception as e:
        if DEBUG:
            print(f"Ошибка поиска: {e}")
        await update.message.reply_text("❌ Ошибка при поиске пользователя")
        return
    
    if not target_user:
        await update.message.reply_text("❌ Пользователь не найден в чате")
        return
    
    target_id = target_user.id
    
    can_change, reason = can_change_level(user_id, target_id, new_level)
    if not can_change:
        await update.message.reply_text(f"❌ {reason}")
        return
    
    old_level = db.get_user_level(target_id)
    db.set_user_level(
        target_id,
        new_level,
        target_user.username,
        target_user.first_name
    )
    
    action = "повышен" if new_level > old_level else "понижен"
    await update.message.reply_text(
        f"✅ Пользователь @{target_user.username} {action}!\n"
        f"{LEVELS[old_level]} → {LEVELS[new_level]}"
    )

async def unmute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    
    if db.get_user_level(user_id) < 3:
        await update.message.reply_text("❌ Только модераторы и выше могут размучивать!")
        return
    
    if not context.args:
        await update.message.reply_text("❌ Укажите @username пользователя")
        return
    
    username = context.args[0].lstrip('@')
    
    target_user = None
    try:
        async for member in context.bot.get_chat_members(chat_id):
            if member.user.username and member.user.username.lower() == username.lower():
                target_user = member.user
                break
    except Exception as e:
        if DEBUG:
            print(f"Ошибка поиска: {e}")
        await update.message.reply_text("❌ Ошибка при поиске пользователя")
        return
    
    if not target_user:
        await update.message.reply_text("❌ Пользователь не найден в чате")
        return
    
    target_id = target_user.id
    
    if user_id != target_id and db.get_user_level(user_id) <= db.get_user_level(target_id):
        await update.message.reply_text("❌ Нельзя размучивать пользователей выше или равного вам уровня!")
        return
    
    try:
        await context.bot.restrict_chat_member(
            chat_id=chat_id,
            user_id=target_id,
            permissions=ChatPermissions(can_send_messages=True)
        )
        await update.message.reply_text(f"✅ Пользователь @{target_user.username} размьючен!")
    except Exception as e:
        if DEBUG:
            print(f"Ошибка размута: {e}")
        await update.message.reply_text("❌ Ошибка при размуте")

async def stats_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    all_users = db.get_all_users()
    total_users = len(all_users)
    
    level_counts = {level: 0 for level in range(1, 7)}
    for user_data in all_users:
        level = user_data['level']
        if level in level_counts:
            level_counts[level] += 1
    
    message = "📊 Статистика бота:\n\n"
    message += f"👥 Всего пользователей: {total_users}\n"
    message += "📈 Распределение по уровням:\n"
    
    for level in range(6, 0, -1):
        message += f"{LEVELS[level]}: {level_counts[level]} пользователей\n"
    
    await update.message.reply_text(message)

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = """
🤖 **Команды бота-модератора:**

📋 **Для всех:**
/start - Информация о боте
/mylevel - Узнать свой уровень
/list - Список пользователей по уровням
/stats - Статистика бота
/help - Эта справка

🛡️ **Для модераторов (уровень 3+):**
/unmute @username - Размутить пользователя

👑 **Для админов (уровень 5+):**
/setlevel @username уровень - Установить уровень
повысить @username уровень - Повысить уровень (в сообщении)
понизить @username уровень - Понизить уровень (в сообщении)

📊 **Система уровней:**
1. 👤 Обычный пользователь
2. 💰 Донатер
3. 🛡️ Младший модератор
4. 🛡️ Модератор
5. 👑 Младший админ
6. 👑 Старший админ

🔒 **Антиспам:**
• 2 сообщения только с эмодзи подряд → мут
• 3 стикера за 10 секунд → мут
    """
    
    await update.message.reply_text(help_text, parse_mode='Markdown')

# === Обработчики сообщений ===
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = update.effective_user.id
        chat_id = update.effective_chat.id
        user = update.effective_user
        
        if user_id == context.bot.id:
            return
        
        db.set_user_level(
            user_id,
            db.get_user_level(user_id),
            user.username,
            user.first_name
        )
        
        await update_chat_owner_level(chat_id, context.bot)
        
        if update.message.sticker:
            await handle_sticker(update, context, user_id)
        elif update.message.text:
            await handle_text(update, context, user_id, chat_id, update.message.text)
            
    except Exception as e:
        if DEBUG:
            print(f"Ошибка в обработчике: {e}")

async def handle_sticker(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int):
    if user_id in SENIOR_ADMIN_IDS:
        return
    
    user_level = db.get_user_level(user_id)
    if user_level < 3:
        db.add_sticker_record(user_id)
        
        sticker_count = db.get_recent_stickers(user_id, STICKER_TIME_WINDOW)
        
        if sticker_count >= STICKER_SPAM_THRESHOLD:
            if DEBUG:
                print(f"🔴 Спам стикерами от {user_id}: {sticker_count} за {STICKER_TIME_WINDOW} сек")
            
            if can_mute_user(context.bot.id, user_id):
                await mute_user(update, context, user_id, "спам стикерами")
                await update.message.delete()
                db.clear_user_history(user_id)

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE, 
                     user_id: int, chat_id: int, message_text: str):
    if message_text.lower().startswith(('повысить', 'понизить')):
        parts = message_text.split()
        if len(parts) != 3:
            await update.message.reply_text("❌ Формат: повысить @username уровень")
            return
        
        username = parts[1].lstrip('@')
        try:
            new_level = int(parts[2])
        except ValueError:
            await update.message.reply_text("❌ Уровень должен быть числом от 1 до 6")
            return
        
        if db.get_user_level(user_id) < 5:
            await update.message.reply_text("❌ Только админы могут менять уровни!")
            return
        
        target_user = None
        try:
            async for member in context.bot.get_chat_members(chat_id):
                if member.user.username and member.user.username.lower() == username.lower():
                    target_user = member.user
                    break
        except:
            await update.message.reply_text("❌ Ошибка при поиске пользователя")
            return
        
        if not target_user:
            await update.message.reply_text("❌ Пользователь не найден в чате")
            return
        
        target_id = target_user.id
        
        can_change, reason = can_change_level(user_id, target_id, new_level)
        if not can_change:
            await update.message.reply_text(f"❌ {reason}")
            return
        
        old_level = db.get_user_level(target_id)
        db.set_user_level(
            target_id,
            new_level,
            target_user.username,
            target_user.first_name
        )
        
        action = "повышен" if new_level > old_level else "понижен"
        await update.message.reply_text(
            f"✅ Пользователь @{target_user.username} {action}!\n"
            f"{LEVELS[old_level]} → {LEVELS[new_level]}"
        )
        return
    
    user_level = db.get_user_level(user_id)
    if user_level < 3 and user_id not in SENIOR_ADMIN_IDS:
        is_spam = is_emoji_only(message_text)
        
        db.add_message_record(user_id, is_spam)
        
        if is_spam:
            recent_messages = db.get_recent_spam_messages(user_id, SPAM_THRESHOLD)
            
            if len(recent_messages) >= SPAM_THRESHOLD and all(recent_messages):
                if DEBUG:
                    print(f"🔴 Спам эмодзи от {user_id}")
                
                if can_mute_user(context.bot.id, user_id):
                    await mute_user(update, context, user_id, "спам эмодзи")
                    await update.message.delete()
                    db.clear_user_history(user_id)

async def mute_user(update: Update, context: ContextTypes.DEFAULT_TYPE, 
                   user_id: int, reason: str):
    try:
        chat_id = update.effective_chat.id
        mute_until = time.time() + MUTE_DURATION
        
        await context.bot.restrict_chat_member(
            chat_id=chat_id,
            user_id=user_id,
            permissions=ChatPermissions(can_send_messages=False),
            until_date=mute_until
        )
        
        db.add_mute_record(user_id, reason, context.bot.id, mute_until)
        
        user_name = update.effective_user.first_name
        
        if "стикер" in reason:
            message_text = f"🚫 Пользователь {user_name} замьючен на {MUTE_DURATION//60} минут за спам стикерами!"
        else:
            message_text = f"🚫 Пользователь {user_name} замьючен на {MUTE_DURATION//60} минут за спам эмодзи!"
        
        await context.bot.send_message(chat_id=chat_id, text=message_text)
        
        db.clear_user_history(user_id)
        
    except Exception as e:
        if DEBUG:
            print(f"Ошибка при муте: {e}")

def main():
    print("="*50)
    print("🤖 Telegram Moderator Bot with Database")
    print(f"📁 Database: {DATABASE_PATH}")
    print("="*50)
    
    try:
        app = Application.builder().token(BOT_TOKEN).build()
        
        app.add_handler(CommandHandler("start", start))
        app.add_handler(CommandHandler("mylevel", mylevel))
        app.add_handler(CommandHandler("list", list_cmd))
        app.add_handler(CommandHandler("setlevel", setlevel))
        app.add_handler(CommandHandler("unmute", unmute))
        app.add_handler(CommandHandler("stats", stats_cmd))
        app.add_handler(CommandHandler("help", help_cmd))
        
        app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_message))
        
        print("✅ Бот запущен. Ctrl+C для остановки")
        print("="*50)
        
        app.run_polling()
        
if __name__ == "__main__":
    main()
