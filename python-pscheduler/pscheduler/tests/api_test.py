"""
test for the api module.
"""

import unittest

from pscheduler.api import (
    api_url,
    api_has_bwctl,
    api_has_pscheduler,
)

from base_test import PschedTestBase


class TestApi(PschedTestBase):
    """
    Api tests.
    """

    def test_api(self):
        """taken from api.__main__"""

        self.assertEqual(
            api_url(host='host.example.com'),
            'https://host.example.com/pscheduler/')
        self.assertEqual(
            api_url(host='host.example.com', path='/both-slash'),
            'https://host.example.com/pscheduler/both-slash')
        self.assertEqual(
            api_url(host='host.example.com', path='both-noslash'),
            'https://host.example.com/pscheduler/both-noslash')

        self.assertFalse(api_has_bwctl(None))
        self.assertFalse(api_has_pscheduler(None))


if __name__ == '__main__':
    unittest.main()
