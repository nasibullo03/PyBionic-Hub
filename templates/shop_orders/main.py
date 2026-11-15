"""Shop Orders — мини-магазин и приём заказов в Telegram.

Покупатель: каталог с фото → корзина → оформление (имя, телефон кнопкой, адрес, комментарий)
→ статус заказа приходит сообщением.
Владелец (ADMIN_IDS): заказы приходят сразу с кнопками «Принят / В пути / Выполнен / Отменён»;
товары добавляются прямо в боте: «➕ Товар» или одной строкой /add Название | 25 | описание.

Переменные:
    BOT_TOKEN
    ADMIN_IDS      — Telegram ID владельцев через запятую (обязательно; узнать свой ID: @userinfobot)
    SHOP_NAME      — название магазина
    CURRENCY       — валюта, по умолчанию «сом.»
    MIN_ORDER      — минимальная сумма заказа (0 = нет)
"""

from __future__ import annotations

import json
import os
import sqlite3
import sys
import threading
import time
from typing import Any

import pybionic_core as core
from i18n import build_reply_language_keyboard, log, parse_lang_choice, set_user_lang, t

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)

BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip()
ADMIN_IDS = core.allowed_ids(os.environ.get("ADMIN_IDS", ""))
SHOP_NAME = os.environ.get("SHOP_NAME", "").strip() or "Shop"
CURRENCY = os.environ.get("CURRENCY", "").strip() or "сом."
try:
    MIN_ORDER = float(os.environ.get("MIN_ORDER", "0") or 0)
except ValueError:
    MIN_ORDER = 0.0

STATUSES = ["new", "accepted", "delivering", "done", "cancelled"]
STATUS_ICON = {"new": "🆕", "accepted": "✅", "delivering": "🚚", "done": "🏁", "cancelled": "❌"}

DB_PATH = core.get_data_dir() / "shop.db"
_db_lock = threading.Lock()


def db() -> sqlite3.Connection:
    c = sqlite3.connect(DB_PATH, check_same_thread=False)
    c.execute("""CREATE TABLE IF NOT EXISTS products (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, price REAL,
        descr TEXT DEFAULT '', photo_id TEXT DEFAULT '', active INTEGER DEFAULT 1, created INTEGER)""")
    c.execute("CREATE TABLE IF NOT EXISTS cart (user_id INTEGER, product_id INTEGER, qty INTEGER, PRIMARY KEY(user_id, product_id))")
    c.execute("""CREATE TABLE IF NOT EXISTS orders (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, username TEXT,
        name TEXT, phone TEXT, address TEXT, comment TEXT, items TEXT, total REAL, status TEXT DEFAULT 'new', created INTEGER)""")
    return c


def q(sql: str, args: tuple = (), one: bool = False) -> Any:
    with _db_lock, db() as c:
        cur = c.execute(sql, args)
        if sql.lstrip().upper().startswith("SELECT"):
            return cur.fetchone() if one else cur.fetchall()
        return cur.lastrowid


def money(v: float) -> str:
    s = f"{v:,.2f}".rstrip("0").rstrip(".").replace(",", " ")
    return f"{s} {CURRENCY}"


def esc(s: Any) -> str:
    return str(s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def parse_price(s: str) -> float | None:
    try:
        v = float(s.replace(" ", "").replace(",", "."))
        return v if v >= 0 else None
    except ValueError:
        return None


def cart_items(uid: int) -> list[tuple[int, str, float, int]]:
    return q("""SELECT p.id, p.name, p.price, c.qty FROM cart c JOIN products p ON p.id=c.product_id
                WHERE c.user_id=? AND p.active=1 ORDER BY p.name""", (uid,))


def main() -> None:
    if not BOT_TOKEN:
        log("err_missing_token")
        return
    if not ADMIN_IDS:
        log("shop_no_admins")
    import telebot
    from telebot import types

    bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")
    state: dict[int, dict[str, Any]] = {}

    def is_admin(uid: int) -> bool:
        return uid in ADMIN_IDS

    def main_kb(uid: int) -> Any:
        kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
        kb.row(types.KeyboardButton(core.btn("btn_catalog", uid)), types.KeyboardButton(core.btn("btn_cart", uid)))
        kb.row(types.KeyboardButton(core.btn("btn_my_orders", uid)), types.KeyboardButton(core.btn("btn_lang", uid)))
        if is_admin(uid):
            kb.row(types.KeyboardButton(core.btn("btn_add_product", uid)), types.KeyboardButton(core.btn("btn_products", uid)),
                   types.KeyboardButton(core.btn("btn_orders", uid)))
        return kb

    def cancel_kb(uid: int, extra: list[Any] | None = None) -> Any:
        kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
        for b in extra or []:
            kb.row(b)
        kb.row(types.KeyboardButton(core.btn("btn_cancel", uid)))
        return kb

    # -- каталог ------------------------------------------------------------
    def show_catalog(chat_id: int, uid: int, edit_msg: int | None = None) -> None:
        rows = q("SELECT id, name, price FROM products WHERE active=1 ORDER BY id")
        if not rows:
            bot.send_message(chat_id, t("shop_catalog_empty", user_id=uid), reply_markup=main_kb(uid))
            return
        kb = types.InlineKeyboardMarkup()
        for pid, name, price in rows[:90]:
            kb.add(types.InlineKeyboardButton(f"{name} — {money(price)}", callback_data=f"p:{pid}"))
        text = t("shop_catalog_title", user_id=uid, shop=esc(SHOP_NAME))
        if edit_msg:
            try:
                bot.edit_message_text(text, chat_id, edit_msg, reply_markup=kb)
                return
            except Exception:
                pass
        bot.send_message(chat_id, text, reply_markup=kb)

    def product_kb(pid: int, uid: int) -> Any:
        kb = types.InlineKeyboardMarkup()
        kb.row(types.InlineKeyboardButton(t("shop_add_to_cart", user_id=uid), callback_data=f"add:{pid}"))
        kb.row(types.InlineKeyboardButton(t("shop_open_cart", user_id=uid), callback_data="cart"),
               types.InlineKeyboardButton(t("shop_back_catalog", user_id=uid), callback_data="cat"))
        return kb

    def show_product(chat_id: int, uid: int, pid: int) -> None:
        row = q("SELECT name, price, descr, photo_id FROM products WHERE id=? AND active=1", (pid,), one=True)
        if not row:
            bot.send_message(chat_id, t("shop_product_gone", user_id=uid))
            return
        name, price, descr, photo = row
        cap = f"<b>{esc(name)}</b>\n{money(price)}" + (f"\n\n{esc(descr)}" if descr else "")
        if photo:
            bot.send_photo(chat_id, photo, caption=cap[:1000], reply_markup=product_kb(pid, uid))
        else:
            bot.send_message(chat_id, cap, reply_markup=product_kb(pid, uid))

    # -- корзина ------------------------------------------------------------
    def cart_view(uid: int) -> tuple[str, Any]:
        items = cart_items(uid)
        if not items:
            return t("shop_cart_empty", user_id=uid), None
        total = sum(p * qn for _, _, p, qn in items)
        lines = [t("shop_cart_title", user_id=uid)]
        kb = types.InlineKeyboardMarkup()
        for pid, name, price, qty in items:
            lines.append(f"• {esc(name)} × {qty} = {money(price * qty)}")
            kb.row(types.InlineKeyboardButton("➖", callback_data=f"dec:{pid}"),
                   types.InlineKeyboardButton(f"{name[:18]} × {qty}", callback_data=f"p:{pid}"),
                   types.InlineKeyboardButton("➕", callback_data=f"inc:{pid}"))
        lines.append(t("shop_total", user_id=uid, total=money(total)))
        kb.row(types.InlineKeyboardButton(t("shop_checkout", user_id=uid), callback_data="checkout"))
        kb.row(types.InlineKeyboardButton(t("shop_clear_cart", user_id=uid), callback_data="clear"),
               types.InlineKeyboardButton(t("shop_back_catalog", user_id=uid), callback_data="cat"))
        return "\n".join(lines), kb

    def show_cart(chat_id: int, uid: int, edit_msg: int | None = None) -> None:
        text, kb = cart_view(uid)
        if edit_msg:
            try:
                bot.edit_message_text(text, chat_id, edit_msg, reply_markup=kb)
                return
            except Exception:
                pass
        bot.send_message(chat_id, text, reply_markup=kb)

    # -- заказы -------------------------------------------------------------
    def order_text(oid: int, uid_for_lang: int, full: bool = True) -> str:
        o = q("SELECT user_id, username, name, phone, address, comment, items, total, status, created FROM orders WHERE id=?", (oid,), one=True)
        user_id, username, name, phone, address, comment, items, total, status, created = o
        lines = [t("shop_order_head", user_id=uid_for_lang, id=oid, icon=STATUS_ICON[status],
                   status=t(f"shop_st_{status}", user_id=uid_for_lang))]
        for it in json.loads(items):
            lines.append(f"• {esc(it['name'])} × {it['qty']} = {money(it['price'] * it['qty'])}")
        lines.append(t("shop_total", user_id=uid_for_lang, total=money(total)))
        if full:
            who = f"@{esc(username)}" if username else f"<a href=\"tg://user?id={user_id}\">{user_id}</a>"
            lines.append(f"\n👤 {esc(name)} ({who})\n📞 {esc(phone)}\n📍 {esc(address)}")
            if comment:
                lines.append(f"💬 {esc(comment)}")
        lines.append("🕒 " + time.strftime("%d.%m %H:%M", time.localtime(created)))
        return "\n".join(lines)

    def admin_kb(oid: int, uid: int) -> Any:
        kb = types.InlineKeyboardMarkup()
        kb.row(*[types.InlineKeyboardButton(STATUS_ICON[s] + " " + t(f"shop_st_{s}", user_id=uid), callback_data=f"st:{oid}:{s}")
                 for s in ("accepted", "delivering")])
        kb.row(*[types.InlineKeyboardButton(STATUS_ICON[s] + " " + t(f"shop_st_{s}", user_id=uid), callback_data=f"st:{oid}:{s}")
                 for s in ("done", "cancelled")])
        return kb

    def place_order(msg: Any, st: dict[str, Any]) -> None:
        uid = msg.from_user.id
        items = cart_items(uid)
        if not items:
            bot.send_message(msg.chat.id, t("shop_cart_empty", user_id=uid), reply_markup=main_kb(uid))
            return
        total = sum(p * qn for _, _, p, qn in items)
        payload = json.dumps([{"id": pid, "name": n, "price": p, "qty": qn} for pid, n, p, qn in items], ensure_ascii=False)
        oid = q("INSERT INTO orders (user_id, username, name, phone, address, comment, items, total, created) VALUES (?,?,?,?,?,?,?,?,?)",
                (uid, msg.from_user.username or "", st["name"], st["phone"], st["address"], st.get("comment", ""), payload, total, int(time.time())))
        q("DELETE FROM cart WHERE user_id=?", (uid,))
        bot.send_message(msg.chat.id, t("shop_order_placed", user_id=uid, id=oid), reply_markup=main_kb(uid))
        for admin in ADMIN_IDS:
            try:
                bot.send_message(admin, t("shop_new_order", user_id=admin) + "\n\n" + order_text(oid, admin), reply_markup=admin_kb(oid, admin))
            except Exception as e:  # noqa: BLE001 — владелец ещё не нажал /start в боте
                log("log_error", err=f"admin {admin}: {e!r}")

    # -- команды ------------------------------------------------------------
    @bot.message_handler(commands=["start"])
    def on_start(msg: Any) -> None:
        uid = msg.from_user.id
        state.pop(uid, None)
        text = t("shop_welcome", user_id=uid, shop=esc(SHOP_NAME))
        if is_admin(uid):
            text += "\n\n" + t("shop_admin_hint", user_id=uid)
        elif not ADMIN_IDS:
            text += "\n\n⚠️ ADMIN_IDS"
        bot.send_message(msg.chat.id, text, reply_markup=main_kb(uid))

    @bot.message_handler(commands=["myid"])
    def on_myid(msg: Any) -> None:
        bot.reply_to(msg, f"<code>{msg.from_user.id}</code>")

    @bot.message_handler(commands=["lang", "language"])
    def on_lang(msg: Any) -> None:
        uid = msg.from_user.id
        bot.reply_to(msg, t("tg_lang_title", user_id=uid),
                     reply_markup=build_reply_language_keyboard(user_id=uid, back_text=core.btn("btn_menu", uid)))

    @bot.message_handler(func=lambda m: bool(m.text and parse_lang_choice(m.text)))
    def on_lang_chosen(msg: Any) -> None:
        uid = msg.from_user.id
        set_user_lang(uid, parse_lang_choice(msg.text) or "en")
        bot.reply_to(msg, t("tg_lang_changed", user_id=uid), reply_markup=main_kb(uid))

    @bot.message_handler(func=lambda m: core.is_btn(m.text, "btn_lang"))
    def on_lang_btn(msg: Any) -> None:
        on_lang(msg)

    @bot.message_handler(func=lambda m: core.is_btn(m.text, "btn_menu", "btn_back", "btn_cancel"))
    def on_cancel(msg: Any) -> None:
        state.pop(msg.from_user.id, None)
        bot.send_message(msg.chat.id, "👌", reply_markup=main_kb(msg.from_user.id))

    @bot.message_handler(func=lambda m: core.is_btn(m.text, "btn_catalog"))
    def on_catalog(msg: Any) -> None:
        show_catalog(msg.chat.id, msg.from_user.id)

    @bot.message_handler(func=lambda m: core.is_btn(m.text, "btn_cart"))
    def on_cart(msg: Any) -> None:
        show_cart(msg.chat.id, msg.from_user.id)

    @bot.message_handler(func=lambda m: core.is_btn(m.text, "btn_my_orders"))
    def on_my_orders(msg: Any) -> None:
        uid = msg.from_user.id
        rows = q("SELECT id FROM orders WHERE user_id=? ORDER BY id DESC LIMIT 10", (uid,))
        if not rows:
            bot.send_message(msg.chat.id, t("shop_no_orders", user_id=uid))
            return
        bot.send_message(msg.chat.id, "\n\n".join(order_text(oid, uid, full=False) for (oid,) in rows))

    # -- владелец -----------------------------------------------------------
    @bot.message_handler(commands=["add"], func=lambda m: is_admin(m.from_user.id))
    def on_add_cmd(msg: Any) -> None:
        uid = msg.from_user.id
        arg = msg.text.split(maxsplit=1)[1] if len(msg.text.split(maxsplit=1)) > 1 else ""
        parts = [p.strip() for p in arg.split("|")]
        if len(parts) >= 2 and parts[0] and parse_price(parts[1]) is not None:
            pid = q("INSERT INTO products (name, price, descr, created) VALUES (?,?,?,?)",
                    (parts[0][:100], parse_price(parts[1]), (parts[2] if len(parts) > 2 else "")[:900], int(time.time())))
            bot.reply_to(msg, t("shop_product_saved", user_id=uid, id=pid, name=esc(parts[0])), reply_markup=main_kb(uid))
            return
        state[uid] = {"step": "p_name"}
        bot.send_message(msg.chat.id, t("shop_ask_p_name", user_id=uid), reply_markup=cancel_kb(uid))

    @bot.message_handler(func=lambda m: is_admin(m.from_user.id) and core.is_btn(m.text, "btn_add_product"))
    def on_add_btn(msg: Any) -> None:
        msg.text = "/add"
        on_add_cmd(msg)

    @bot.message_handler(commands=["products"], func=lambda m: is_admin(m.from_user.id))
    def on_products(msg: Any) -> None:
        send_products_admin(msg.chat.id, msg.from_user.id)

    @bot.message_handler(func=lambda m: is_admin(m.from_user.id) and core.is_btn(m.text, "btn_products"))
    def on_products_btn(msg: Any) -> None:
        send_products_admin(msg.chat.id, msg.from_user.id)

    def products_admin_view(uid: int) -> tuple[str, Any]:
        rows = q("SELECT id, name, price, active FROM products ORDER BY id")
        if not rows:
            return t("shop_catalog_empty", user_id=uid), None
        kb = types.InlineKeyboardMarkup()
        for pid, name, price, active in rows[:60]:
            kb.row(types.InlineKeyboardButton(("" if active else "🙈 ") + f"{name[:20]} — {money(price)}", callback_data=f"p:{pid}"),
                   types.InlineKeyboardButton("💲", callback_data=f"price:{pid}"),
                   types.InlineKeyboardButton("👁" if not active else "🙈", callback_data=f"hide:{pid}"),
                   types.InlineKeyboardButton("🗑", callback_data=f"pdel:{pid}"))
        return t("shop_products_admin", user_id=uid), kb

    def send_products_admin(chat_id: int, uid: int) -> None:
        text, kb = products_admin_view(uid)
        bot.send_message(chat_id, text, reply_markup=kb)

    @bot.message_handler(commands=["orders"], func=lambda m: is_admin(m.from_user.id))
    def on_orders(msg: Any) -> None:
        uid = msg.from_user.id
        rows = q("SELECT id FROM orders WHERE status IN ('new','accepted','delivering') ORDER BY id DESC LIMIT 15")
        if not rows:
            bot.send_message(msg.chat.id, t("shop_no_active_orders", user_id=uid))
            return
        for (oid,) in reversed(rows):
            bot.send_message(msg.chat.id, order_text(oid, uid), reply_markup=admin_kb(oid, uid))

    @bot.message_handler(func=lambda m: is_admin(m.from_user.id) and core.is_btn(m.text, "btn_orders"))
    def on_orders_btn(msg: Any) -> None:
        on_orders(msg)

    # -- пошаговые формы ----------------------------------------------------
    @bot.message_handler(content_types=["text", "photo", "contact"], func=lambda m: m.from_user.id in state)
    def on_step(msg: Any) -> None:
        uid = msg.from_user.id
        st = state[uid]
        step = st["step"]
        text = (msg.text or "").strip()
        skip = text in ("-", "—") or core.is_btn(text, "btn_skip")

        def ask(next_step: str, key: str, kb: Any = None) -> None:
            st["step"] = next_step
            bot.send_message(msg.chat.id, t(key, user_id=uid), reply_markup=kb or cancel_kb(uid))

        skip_kb = cancel_kb(uid, [types.KeyboardButton(core.btn("btn_skip", uid))])
        if step == "p_name" and text:
            st["name"] = text[:100]
            ask("p_price", "shop_ask_p_price")
        elif step == "p_price":
            price = parse_price(text)
            if price is None:
                bot.reply_to(msg, t("shop_bad_price", user_id=uid))
                return
            st["price"] = price
            ask("p_descr", "shop_ask_p_descr", skip_kb)
        elif step == "p_descr":
            st["descr"] = "" if skip else text[:900]
            ask("p_photo", "shop_ask_p_photo", skip_kb)
        elif step == "p_photo":
            photo = msg.photo[-1].file_id if msg.photo else ""
            if not photo and not skip:
                bot.reply_to(msg, t("shop_ask_p_photo", user_id=uid))
                return
            pid = q("INSERT INTO products (name, price, descr, photo_id, created) VALUES (?,?,?,?,?)",
                    (st["name"], st["price"], st["descr"], photo, int(time.time())))
            state.pop(uid, None)
            bot.send_message(msg.chat.id, t("shop_product_saved", user_id=uid, id=pid, name=esc(st["name"])), reply_markup=main_kb(uid))
        elif step == "p_newprice":
            price = parse_price(text)
            if price is None:
                bot.reply_to(msg, t("shop_bad_price", user_id=uid))
                return
            q("UPDATE products SET price=? WHERE id=?", (price, st["pid"]))
            state.pop(uid, None)
            bot.send_message(msg.chat.id, "✅ " + money(price), reply_markup=main_kb(uid))
            send_products_admin(msg.chat.id, uid)
        elif step == "c_name" and text:
            st["name"] = text[:80]
            kb = cancel_kb(uid, [types.KeyboardButton(t("shop_share_phone", user_id=uid), request_contact=True)])
            ask("c_phone", "shop_ask_phone", kb)
        elif step == "c_phone":
            phone = msg.contact.phone_number if msg.contact else text
            if len("".join(ch for ch in phone if ch.isdigit())) < 7:
                bot.reply_to(msg, t("shop_bad_phone", user_id=uid))
                return
            st["phone"] = phone[:30]
            ask("c_address", "shop_ask_address")
        elif step == "c_address" and text:
            st["address"] = text[:300]
            ask("c_comment", "shop_ask_comment", skip_kb)
        elif step == "c_comment":
            st["comment"] = "" if skip else text[:300]
            st["step"] = "c_confirm"
            items = cart_items(uid)
            total = sum(p * qn for _, _, p, qn in items)
            lines = [t("shop_confirm_title", user_id=uid)]
            lines += [f"• {esc(n)} × {qn} = {money(p * qn)}" for _, n, p, qn in items]
            lines.append(t("shop_total", user_id=uid, total=money(total)))
            lines.append(f"\n👤 {esc(st['name'])}\n📞 {esc(st['phone'])}\n📍 {esc(st['address'])}" + (f"\n💬 {esc(st['comment'])}" if st["comment"] else ""))
            kb = types.InlineKeyboardMarkup()
            kb.row(types.InlineKeyboardButton(t("shop_confirm_btn", user_id=uid), callback_data="confirm"),
                   types.InlineKeyboardButton(t("shop_cancel_order_btn", user_id=uid), callback_data="abort"))
            bot.send_message(msg.chat.id, t("shop_almost_done", user_id=uid), reply_markup=types.ReplyKeyboardRemove())
            bot.send_message(msg.chat.id, "\n".join(lines), reply_markup=kb)
        else:
            bot.reply_to(msg, t("shop_step_hint", user_id=uid))

    # -- кнопки под сообщениями ---------------------------------------------
    @bot.callback_query_handler(func=lambda c: True)
    def on_cb(c: Any) -> None:
        uid, chat_id, mid = c.from_user.id, c.message.chat.id, c.message.message_id
        act, _, arg = (c.data or "").partition(":")
        try:
            if act == "p":
                bot.answer_callback_query(c.id)
                show_product(chat_id, uid, int(arg))
            elif act == "cat":
                bot.answer_callback_query(c.id)
                show_catalog(chat_id, uid)
            elif act == "cart":
                bot.answer_callback_query(c.id)
                show_cart(chat_id, uid)
            elif act in ("add", "inc"):
                q("INSERT INTO cart VALUES (?,?,1) ON CONFLICT(user_id, product_id) DO UPDATE SET qty=MIN(qty+1, 99)", (uid, int(arg)))
                bot.answer_callback_query(c.id, t("shop_added", user_id=uid))
                if act == "inc":
                    show_cart(chat_id, uid, mid)
            elif act == "dec":
                q("UPDATE cart SET qty=qty-1 WHERE user_id=? AND product_id=?", (uid, int(arg)))
                q("DELETE FROM cart WHERE qty<=0")
                bot.answer_callback_query(c.id)
                show_cart(chat_id, uid, mid)
            elif act == "clear":
                q("DELETE FROM cart WHERE user_id=?", (uid,))
                bot.answer_callback_query(c.id)
                show_cart(chat_id, uid, mid)
            elif act == "checkout":
                items = cart_items(uid)
                total = sum(p * qn for _, _, p, qn in items)
                if not items:
                    bot.answer_callback_query(c.id, t("shop_cart_empty", user_id=uid), show_alert=True)
                    return
                if MIN_ORDER and total < MIN_ORDER:
                    bot.answer_callback_query(c.id, t("shop_min_order", user_id=uid, min=money(MIN_ORDER)), show_alert=True)
                    return
                bot.answer_callback_query(c.id)
                state[uid] = {"step": "c_name"}
                bot.send_message(chat_id, t("shop_ask_name", user_id=uid), reply_markup=cancel_kb(uid))
            elif act == "confirm":
                st = state.pop(uid, None)
                bot.answer_callback_query(c.id)
                bot.edit_message_reply_markup(chat_id, mid, reply_markup=None)
                if st and st.get("step") == "c_confirm":
                    c.message.from_user = c.from_user
                    place_order(c.message, st)
            elif act == "abort":
                state.pop(uid, None)
                bot.answer_callback_query(c.id)
                bot.edit_message_reply_markup(chat_id, mid, reply_markup=None)
                bot.send_message(chat_id, "👌", reply_markup=main_kb(uid))
            elif act == "st" and is_admin(uid):
                oid_s, _, status = arg.partition(":")
                oid = int(oid_s)
                if status not in STATUSES:
                    return
                q("UPDATE orders SET status=? WHERE id=?", (status, oid))
                bot.answer_callback_query(c.id, STATUS_ICON[status])
                final = status in ("done", "cancelled")
                bot.edit_message_text(order_text(oid, uid), chat_id, mid, reply_markup=None if final else admin_kb(oid, uid))
                cust = q("SELECT user_id FROM orders WHERE id=?", (oid,), one=True)[0]
                try:
                    bot.send_message(cust, t("shop_status_changed", user_id=cust, id=oid, icon=STATUS_ICON[status],
                                             status=t(f"shop_st_{status}", user_id=cust)))
                except Exception as e:  # noqa: BLE001
                    log("log_error", err=repr(e))
            elif act == "price" and is_admin(uid):
                state[uid] = {"step": "p_newprice", "pid": int(arg)}
                bot.answer_callback_query(c.id)
                bot.send_message(chat_id, t("shop_ask_p_price", user_id=uid), reply_markup=cancel_kb(uid))
            elif act == "hide" and is_admin(uid):
                q("UPDATE products SET active=1-active WHERE id=?", (int(arg),))
                bot.answer_callback_query(c.id)
                text, kb = products_admin_view(uid)
                bot.edit_message_text(text, chat_id, mid, reply_markup=kb)
            elif act == "pdel" and is_admin(uid):
                q("DELETE FROM products WHERE id=?", (int(arg),))
                q("DELETE FROM cart WHERE product_id=?", (int(arg),))
                bot.answer_callback_query(c.id, "🗑")
                text, kb = products_admin_view(uid)
                bot.edit_message_text(text, chat_id, mid, reply_markup=kb)
            else:
                bot.answer_callback_query(c.id)
        except Exception as e:  # noqa: BLE001
            log("log_error", err=repr(e))
            try:
                bot.answer_callback_query(c.id)
            except Exception:
                pass

    log("log_started_tg", shop=SHOP_NAME, admins=len(ADMIN_IDS))
    core.start_polling(bot, skip_pending=True, timeout=30, long_polling_timeout=30)


if __name__ == "__main__":
    main()
