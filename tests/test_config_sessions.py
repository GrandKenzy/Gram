"""Regression coverage for configuration changes across language sessions."""
import unittest

from gram import config
from gram.sessions import Session


class TestSessionConfiguration(unittest.TestCase):
    def setUp(self):
        self.previous = config.save()
        self.addCleanup(config.load, self.previous)

    def test_migration_restores_logging_policy_and_load_reapplies_it(self):
        config.INFO_GENERATE_LOGFILE_ON_ERROR = False
        config.INFO_INIT = False
        config.ERROR_EXIT_ON_ERROR = True
        session = Session('logging-language', 'Many')
        session.init()

        config.INFO_GENERATE_LOGFILE_ON_ERROR = True
        config.INFO_INIT = True
        config.ERROR_EXIT_ON_ERROR = False
        session.migrate()

        self.assertFalse(config.INFO_GENERATE_LOGFILE_ON_ERROR)
        self.assertFalse(config.INFO_INIT)
        self.assertTrue(config.ERROR_EXIT_ON_ERROR)

        session.load()
        self.assertTrue(config.INFO_GENERATE_LOGFILE_ON_ERROR)
        self.assertTrue(config.INFO_INIT)
        self.assertFalse(config.ERROR_EXIT_ON_ERROR)

    def test_loading_another_session_does_not_keep_previous_logging_policy(self):
        first = Session('first', 'Many')
        first.init()
        config.INFO_GENERATE_LOGFILE_ON_ERROR = True
        first.migrate()

        second = Session('second', 'Many')
        second.init()
        config.INFO_GENERATE_LOGFILE_ON_ERROR = False
        second.migrate()

        first.load()
        self.assertTrue(config.INFO_GENERATE_LOGFILE_ON_ERROR)
        second.load()
        self.assertFalse(config.INFO_GENERATE_LOGFILE_ON_ERROR)
