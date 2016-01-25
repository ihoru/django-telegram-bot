#!/usr/bin/env python
# -*- coding: utf-8 -*-
from django.test import TestCase
from telegrambot.models import Update, User, Chat
from tests import factories
from django.core.urlresolvers import reverse
from rest_framework import status
from telegram.replykeyboardhide import ReplyKeyboardHide
from telegrambot import conf
try:
    from unittest import mock
except ImportError:
    import mock  # noqa

class BaseTestBot(TestCase):
    webhook_url = reverse('telegram-webhook')

    def setUp(self):
        self.update = factories.UpdateFactory()
        self.kwargs = {'content_type': 'application/json', }
        
    def assertUser(self, model_user, user):
        self.assertEqual(model_user.id, user.id)
        self.assertEqual(model_user.first_name, user.first_name)
        self.assertEqual(model_user.last_name, user.last_name)
        self.assertEqual(model_user.username, user.username)
        
    def assertChat(self, model_chat, chat):        
        self.assertEqual(model_chat.id, chat.id)
        self.assertEqual(model_chat.type, chat.type)
        self.assertEqual(model_chat.title, chat.title)
        self.assertEqual(model_chat.username, chat.username)
        self.assertEqual(model_chat.first_name, chat.first_name)
        self.assertEqual(model_chat.last_name, chat.last_name)
        
    def assertMessage(self, model_message, message):        
        self.assertEqual(model_message.message_id, message.message_id)
        self.assertUser(model_message.from_user, message.from_user)
        self.assertChat(model_message.chat, message.chat)
        #  TODO: problems with UTCs
        #  self.assertEqual(model_message.date, message.date)
        self.assertEqual(model_message.text, message.text)
        
    def assertUpdate(self, model_update, update):
        self.assertEqual(model_update.update_id, update.update_id)
        self.assertMessage(model_update.message, update.message)
        
    def assertInKeyboard(self, button, keyboard):
        found = False
        for line in keyboard:
            if button in line:
                found = True
                break
        self.assertTrue(found)
        
    def assertBotResponse(self, mock_send, command):
        args, kwargs = mock_send.call_args
        self.assertEqual(1, mock_send.call_count)
        self.assertEqual(kwargs['chat_id'], self.update.message.chat.id)
        self.assertEqual(kwargs['parse_mode'], command['values']['parse_mode'])
        if not command['values']['reply_markup']:
            self.assertTrue(isinstance(kwargs['reply_markup'], ReplyKeyboardHide))
        else:
            self.assertInKeyboard(command['values']['reply_markup'], kwargs['reply_markup'].keyboard)
                
        self.assertIn(command['values']['text'], kwargs['text'].decode('utf-8'))

    def _test_command_ok(self, command, update=None, number=1):
        if not update:
            update = self.update
        with mock.patch("telegram.bot.Bot.sendMessage", callable=mock.MagicMock()) as mock_send:
            update.message.text = "/" + command['command']
            response = self.client.post(self.webhook_url, update.to_json(), **self.kwargs)
            #  Check response 200 OK
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            #  Check  
            self.assertBotResponse(mock_send, command)
            self.assertEqual(number, Update.objects.count())
            self.assertUpdate(Update.objects.get(update_id=update.update_id), update)
        

class TestBotCommands(BaseTestBot): 
    
    start = {'command': 'start',
             'values': {'parse_mode': 'Markdown',
                        'reply_markup': '',
                        'text': "Start command"
                        }
             }
    
    unknown = {'command': 'no_defined',
               'values': {'parse_mode': 'Markdown',
                          'reply_markup': '',
                          'text': "Unknown command"
                          }
               }
    
    author_list = {'command': 'author',
                   'values': {'parse_mode': 'Markdown',
                              'reply_markup': '/author author_1',
                              'text': "Select from list:\nauthor_1\nauthor_2"
                              }   
                   }
    author_inverse_list = {'command': 'author_inverse',
                           'values': {'parse_mode': 'Markdown',
                                      'reply_markup': '/author author_1',
                                      'text': "Select from list:\nauthor_2\nauthor_1"
                                      }   
                           }
    
    author_detail = {'command': 'author author_1',
                     'values': {'parse_mode': 'Markdown',
                                'reply_markup': '',
                                'text': "Author name:author_1"
                                }   
                     }
    
    author_list_query = {'command': 'author_query',
                         'values': {'parse_mode': 'Markdown',
                                    'reply_markup': '/author author_1',
                                    'text': "Select from list:\nauthor_1\nauthor_2"
                                    }   
                         }
    
    author_detail_query = {'command': 'author_query author_1',
                           'values': {'parse_mode': 'Markdown',
                                      'reply_markup': '',
                                      'text': "Author name:author_1"
                                      }   
                           }
    
    def test_webhook(self):
        #  change conf to set webhook
        conf.TELEGRAM_BOT_TASKS = False
        self._test_command_ok(self.start)

    def test_start(self):
        self._test_command_ok(self.start)
        
    def test_unknown(self):
        self._test_command_ok(self.unknown)
        
    def test_author_list(self):
        factories.AuthorFactory(name="author_1")
        factories.AuthorFactory(name="author_2")
        self._test_command_ok(self.author_list)
        
    def test_author_inverse_list(self):
        factories.AuthorFactory(name="author_1")
        factories.AuthorFactory(name="author_2")
        self._test_command_ok(self.author_inverse_list)    
    
    def test_author_detail(self):
        factories.AuthorFactory(name="author_1")
        self._test_command_ok(self.author_detail)
        
    def test_author_list_queryset(self):
        factories.AuthorFactory(name="author_1")
        factories.AuthorFactory(name="author_2")
        self._test_command_ok(self.author_list_query)
        
    def test_author_detail_queryset(self):
        factories.AuthorFactory(name="author_1")
        self._test_command_ok(self.author_detail_query)
        
    def test_several_commands_from_same_user_and_chat(self):
        self._test_command_ok(self.start)
        user = self.update.message.from_user
        chat = self.update.message.chat
        update_2 = factories.UpdateFactory()
        update_2.message.from_user = user
        update_2.message.chat = chat
        self._test_command_ok(self.unknown, update_2, 2)
        self.assertEqual(User.objects.count(), 1)
        self.assertEqual(Chat.objects.count(), 1)