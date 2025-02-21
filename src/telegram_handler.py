from telethon import TelegramClient
import asyncio
import os
from queue import Queue
import threading
import time

class TelegramHandler:
    def __init__(self, config, targets=None, info_logger=None, error_logger=None):
        self.config = config
        self.targets = targets or config['telegram']['default_targets']
        self.info_logger = info_logger
        self.error_logger = error_logger
        self.message_queue = Queue()
        self.telegram_ready = threading.Event()
        self.telegram_client = None
        self._running = True
        
        # Start Telegram client in a separate thread
        self.telegram_thread = threading.Thread(target=self.run_telegram_client)
        self.telegram_thread.daemon = True

        # Add download event listener
        def handle_download(download):
            file_path = os.path.join('channel_images', download.suggested_filename)
            print(f"Starting download of file: {download.suggested_filename}")
            print(f"Saving to path: {file_path}")
            download.save_as(file_path)
            print(f"File downloaded successfully to: {file_path}")
            
            # ارسال فوری به تلگرام
            if self.current_message_text:
                self.queue_message(self.current_message_text, file_path)
                print(f"Message and image queued for Telegram: {file_path}")
        
        self.handle_download = handle_download

    def connect(self):
        """Start Telegram client thread"""
        self.telegram_thread.start()
        self.info_logger.info("Waiting for Telegram login...")
        if not self.telegram_ready.wait(timeout=60):
            raise Exception("Telegram login timeout")

    def run_telegram_client(self):
        """Run Telegram client in a separate thread"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        async def run_client():
            try:
                await asyncio.sleep(1)
                
                self.telegram_client = TelegramClient(
                    self.config['telegram'].get('session_name', 'eitaa_forwarder_session'),
                    self.config['telegram']['api_id'],
                    self.config['telegram']['api_hash']
                )
                await self.telegram_client.connect()
                self.info_logger.info("Please complete Telegram login if needed...")
                await self.telegram_client.start()
                self.info_logger.info("Telegram client started successfully")
                
                self.telegram_ready.set()
                
                while self._running:
                    if not self.message_queue.empty():
                        msg_data = self.message_queue.get()
                        await self._send_message(msg_data)
                    await asyncio.sleep(0.1)
                
                if self.telegram_client:
                    await self.telegram_client.disconnect()
                
            except Exception as e:
                self.error_logger.error(f"Telegram client error: {e}")
                
        loop.run_until_complete(run_client())

    def queue_message(self, message, file_path=None, specific_targets=None):
        """Add message to queue with optional file and specific targets"""
        try:
            targets = specific_targets if specific_targets else self.targets
            self.message_queue.put({
                'message': message,
                'file_path': file_path,
                'targets': targets
            })
            self.info_logger.info(f"Message queued for targets: {targets}")
        except Exception as e:
            self.error_logger.error(f"Error queueing message: {e}")

    async def _send_message(self, msg_data):
        """Send a single message"""
        try:
            targets = msg_data['targets']
            message = msg_data['message']
            file_path = msg_data.get('file_path')

            for target in targets:
                try:
                    if file_path and os.path.exists(file_path):
                        await self.telegram_client.send_file(
                            target,
                            file_path,
                            caption=message
                        )
                        self.info_logger.info(f"Sent message with file to {target}")
                    else:
                        await self.telegram_client.send_message(
                            target,
                            message
                        )
                        self.info_logger.info(f"Sent message to {target}")
                    
                except Exception as e:
                    self.error_logger.error(f"Error sending message to {target}: {e}")
                    continue
        except Exception as e:
            self.error_logger.error(f"Error sending message: {e}")

    def disconnect(self):
        """Stop Telegram client"""
        try:
            self._running = False
            if self.telegram_thread.is_alive():
                self.telegram_thread.join(timeout=5)
            
            if self.telegram_client:
                try:
                    self.telegram_client._sender.disconnect()
                    self.telegram_client = None
                except:
                    pass
            
            self.info_logger.info("Telegram client disconnected successfully")
        except Exception as e:
            self.error_logger.error(f"Error during telegram disconnect: {e}") 