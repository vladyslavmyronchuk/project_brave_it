import serial
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
import serial.tools.list_ports
from dotenv import load_dotenv
import os
import json
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

from aiogram.types import FSInputFile

load_dotenv()

TOKEN = os.getenv("TOKEN")
BAUD_RATE = 9600
DATA_FILE = "sensor_data.json"  

class TelegramBot:
    def __init__(self, token):
        self.bot = Bot(token=token)
        self.dp = Dispatcher()
        self.user_ports = {}  # Збереження портів користувачів
        self.serial_connections = {}  # Збереження серійних з'єднань

        self.dp.message.register(self.start, Command("start"))
        self.dp.message.register(self.connect_device, Command("connect_device"))
        self.dp.message.register(self.get_data, Command("info"))
        self.dp.message.register(self.get_port, Command("getport"))
        self.dp.message.register(self.stat, Command("stat"))
        self.dp.message.register(self.graph, Command("graph"))
        self.dp.message.register(self.unknown_command)
        self.dp.callback_query.register(self.handle_callback)

    async def set_bot_commands(self):
        commands = [
            types.BotCommand(command="start", description="🔰 Запуск бота"),
            types.BotCommand(command="connect_device", description="🔌 Підключити пристрій"),
            types.BotCommand(command="info", description="ℹ Отримати дані"),
            types.BotCommand(command="getport", description="🖥 Переглянути порти"),
            types.BotCommand(command="stat", description="📊 Середні показники"),
            types.BotCommand(command="graph", description="📈 Побудувати графік")
        ]
        await self.bot.set_my_commands(commands)

    async def start(self, message: Message):
        markup = types.InlineKeyboardMarkup(inline_keyboard=[ 
            [types.InlineKeyboardButton(text="🔌 Підключити девайс", callback_data="connect_device")]
        ])
        await message.answer("Привіт! Щоб підключити термогігрометр, натисніть кнопку нижче:", reply_markup=markup)

    async def handle_callback(self, callback: CallbackQuery):
        if callback.data == "connect_device":
            await self.connect_device(callback)
        elif callback.data == "stat_5minutes":
            await self.show_statistics(callback.message, timedelta(minutes=5))
        elif callback.data == "stat_1hour":
            await self.show_statistics(callback.message, timedelta(hours=1))
        elif callback.data == "stat_4hours":
            await self.show_statistics(callback.message, timedelta(hours=4))
        elif callback.data == "stat_12hours":
            await self.show_statistics(callback.message, timedelta(hours=12))
        elif callback.data == "graph_5minutes":
            await self.send_graph(callback.message, timedelta(minutes=5))
        elif callback.data == "graph_30minutes":
            await self.send_graph(callback.message, timedelta(minutes=30))
        elif callback.data == "graph_3hours":
            await self.send_graph(callback.message, timedelta(hours=3))
        elif callback.data == "graph_12hours":
            await self.send_graph(callback.message, timedelta(hours=12))


    async def get_port(self, message: Message):
        ports = serial.tools.list_ports.comports()
        usb_ports = [port for port in ports if 'USB' in port.description]
        for port in usb_ports:
            await message.answer(f"Назва порту:{port.device}, Опис: {port.description}")

    async def connect_device(self, event):
        user_id = event.from_user.id
        message = event.message if isinstance(event, CallbackQuery) else event
        ports = serial.tools.list_ports.comports()
        usb_ports = [port for port in ports if 'USB' in port.description]

        if not usb_ports:
            await message.answer("❌ Не знайдено доступних USB портів!")
            return

        for port in usb_ports:
            try:
                ser = serial.Serial(port.device, BAUD_RATE, timeout=3, write_timeout=1, dsrdtr=False, rtscts=False)
                ser.dtr = False
                ser.rts = False
                ser.flushInput()

                self.user_ports[user_id] = port.device
                self.serial_connections[user_id] = ser

                await message.answer(f"✅ Порт {port.device} збережено та підключено!")

                # Запускаємо моніторинг після підключення пристрою
                asyncio.create_task(self.monitor_sensor(user_id))

                break

            except serial.SerialException:
                continue

        else:
            await message.answer("❌ Не вдалося підключитися до будь-якого з доступних портів. Спробуйте ще раз.")

    async def get_data(self, message: Message):
        user_id = message.from_user.id
        if user_id not in self.serial_connections:
            await message.answer("⚠ Ви не вказали порт! Використовуйте /connect_device, щоб підключити пристрій.")
            return

        ser = self.serial_connections[user_id]

        try:
            ser.flushInput()
            ser.write(b"GET\n")  # Відправляємо запит на дані
            await asyncio.sleep(2)  # Чекаємо відповідь

            info = ser.readline().decode().strip()
            print(f"Отримано дані: {info}")  # Логування

            if not info:
                await message.answer("❌ Пристрій не відповідає!")
                return

            if info == "ERROR":
                await message.answer("❌ Помилка зчитування даних з датчика!")
                return

            parts = info.split()
            if len(parts) == 2:
                try:
                    temp, hum = map(float, parts)
                    response = f"🌡 Температура: {temp}°C\n💧 Вологість: {hum}%"

                    
                    self.save_data_to_json(temp, hum)

                    await self.bot.send_message(user_id, response)
                except ValueError:
                    await self.bot.send_message(user_id, "❌ Помилка розпізнавання даних! Переконайтеся, що формат правильний.")
            else:
                await self.bot.send_message(user_id, "❌ Помилка формату даних від Пристрою!")

        except serial.SerialException:
            await self.bot.send_message(user_id, f"❌ Втрачене з'єднання з портом {self.user_ports[user_id]}!")

    def save_data_to_json(self, temp, hum):
        data = {
            "timestamp": datetime.now().isoformat(),
            "temperature": temp,
            "humidity": hum
        }

        try:
            with open(DATA_FILE, "r") as file:
                all_data = json.load(file)
        except FileNotFoundError:
            all_data = []

        all_data.append(data)

        with open(DATA_FILE, "w") as file:
            json.dump(all_data, file, indent=4)

    async def monitor_sensor(self, user_id: int):
        while True:
            if user_id in self.serial_connections:
                ser = self.serial_connections[user_id]

                try:
                    ser.flushInput()
                    ser.write(b"GET\n")  # Запит на отримання даних
                    await asyncio.sleep(2)  # Чекати відповіді від Arduino

                    info = ser.readline().decode().strip()
                    print(f"Отримано дані: {info}")  # Логування

                    if not info:
                        continue

                    if info == "ERROR":
                        continue

                    parts = info.split()
                    if len(parts) == 2:
                        try:
                            temp, hum = map(float, parts)  # Перетворення на числа
                            self.save_data_to_json(temp, hum)

                            # Якщо температура або вологість виходять за межі, надсилаємо повідомлення
                            if temp > 27 or hum < 35:
                                await self.bot.send_message(user_id, f"⚠ Увага: Підвищена температура ({temp}°C) або низька вологість ({hum}%)!")

                            if temp < 18 or hum > 70:
                                await self.bot.send_message(user_id, f"⚠ Увага: Низька температура ({temp}°C) або висока вологість ({hum}%)!")

                        except ValueError:
                            continue

                except serial.SerialException:
                    continue

            await asyncio.sleep(10)  # Перевіряємо дані кожні 10 секунд

    async def stat(self, message: Message):
        markup = types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text="📅 За 5 хвилин", callback_data="stat_5minutes")],
            [types.InlineKeyboardButton(text="📅 За 1 годину", callback_data="stat_1hour")],
            [types.InlineKeyboardButton(text="📅 За 4 години", callback_data="stat_4hours")],
            [types.InlineKeyboardButton(text="📅 За 12 годин", callback_data="stat_12hours")]
        ])
        await message.answer("Оберіть період для переляду середніх показників📅:", reply_markup=markup)

   
    async def show_statistics(self, message: Message, time_range: timedelta):
        try:
            with open(DATA_FILE, "r") as file:
                all_data = json.load(file)
        except FileNotFoundError:
            await message.answer("❌ Немає даних для статистики!")
            return

        now = datetime.now()
        filtered_data = [entry for entry in all_data if now - datetime.fromisoformat(entry["timestamp"]) <= time_range]

        if not filtered_data:
            await message.answer("❌ Немає даних за обраний період!")
            return

        avg_temp = sum(entry["temperature"] for entry in filtered_data) / len(filtered_data)
        avg_hum = sum(entry["humidity"] for entry in filtered_data) / len(filtered_data)

        await message.answer(f"📊 Середня температура: {avg_temp:.2f}°C\n💧 Середня вологість: {avg_hum:.2f}%")

    async def graph(self, message: Message):
        markup = types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text="📈 За 5 хвилин", callback_data="graph_5minutes")],
            [types.InlineKeyboardButton(text="📈 За 30 хвилин", callback_data="graph_30minutes")],
            [types.InlineKeyboardButton(text="📈 За 3 години", callback_data="graph_3hours")],
            [types.InlineKeyboardButton(text="📈 За 12 годин", callback_data="graph_12hours")]
        ])
        await message.answer("Оберіть період для графіка:", reply_markup=markup)

    async def send_graph(self, message: Message,time_range:timedelta):
        graph_file = self.plot_graph(time_range)
        if graph_file:
            photo = FSInputFile(graph_file)
            await message.answer_photo(photo)
        else:
            await message.answer("❌ Немає даних для побудови графіка!")
            

    def plot_graph(self, time_range: timedelta):
        try:
            with open(DATA_FILE, "r") as file:
                all_data = json.load(file)
        except FileNotFoundError:
            return None

        now = datetime.now()
        filtered_data = [entry for entry in all_data if now - datetime.fromisoformat(entry["timestamp"]) <= time_range]

        if not filtered_data:
            return None

        try:
            timestamps = [datetime.strptime(entry["timestamp"], "%Y-%m-%dT%H:%M:%S.%f") for entry in filtered_data]
        except ValueError:
            timestamps = [datetime.strptime(entry["timestamp"], "%Y-%m-%dT%H:%M:%S") for entry in filtered_data]

        temperatures = [entry["temperature"] for entry in filtered_data]
        humidities = [entry["humidity"] for entry in filtered_data]

        fig, ax1 = plt.subplots()
        ax1.set_xlabel('Час')
        ax1.set_ylabel('Температура (°C)', color='tab:red')
        ax1.plot(timestamps, temperatures, color='tab:red', label="Температура")
        ax1.tick_params(axis='y', labelcolor='tab:red')

        ax2 = ax1.twinx()
        ax2.set_ylabel('Вологість (%)', color='tab:blue')
        ax2.plot(timestamps, humidities, color='tab:blue', label="Вологість")
        ax2.tick_params(axis='y', labelcolor='tab:blue')

        ax1.xaxis.set_major_locator(mdates.AutoDateLocator())
        ax1.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M:%S'))
        plt.xticks(rotation=45, ha="right")
        fig.tight_layout()

        graph_filename = "sensor_graph.png"
        plt.savefig(graph_filename)
        plt.close()

        return graph_filename
    
    
    async def unknown_command(self, message: Message):
        await message.answer("❌ Невідома команда. Використовуйте /info ,/connect_device,/getport,/graph,/stat")

    async def run(self):
        await self.set_bot_commands()  # Додаємо команди в меню
        await self.dp.start_polling(self.bot)


if __name__ == "__main__":
    bot = TelegramBot(TOKEN)
    asyncio.run(bot.run())
