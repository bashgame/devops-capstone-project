"""
Account API Service Test Suite

Test cases can be run with the following:
  nosetests -v --with-spec --spec-color
  coverage report -m
"""
import os
import logging
from unittest import TestCase
from tests.factories import AccountFactory
from service.common import status  # HTTP Status Codes
from service.models import db, Account, init_db
from service.routes import app
from service import talisman

DATABASE_URI = os.getenv(
    "DATABASE_URI", "postgresql://postgres:postgres@localhost:5432/postgres"
)

BASE_URL = "/accounts"
HTTPS_ENVIRON = {'wsgi.url_scheme': 'https'}

######################################################################
#  T E S T   C A S E S
######################################################################


class TestAccountService(TestCase):
    """Account Service Tests"""

    @classmethod
    def setUpClass(cls):
        """Run once before all tests"""
        app.config["TESTING"] = True
        app.config["DEBUG"] = False
        app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URI
        app.logger.setLevel(logging.CRITICAL)
        init_db(app)
        talisman.force_https = False

    @classmethod
    def tearDownClass(cls):
        """Runs once before test suite"""

    def setUp(self):
        """Runs before each test"""
        db.session.query(Account).delete()  # clean up the last tests
        db.session.commit()

        self.client = app.test_client()

    def tearDown(self):
        """Runs once after each test case"""
        db.session.remove()

    ######################################################################
    #  H E L P E R   M E T H O D S
    ######################################################################

    def _create_accounts(self, count):
        """Factory method to create accounts in bulk"""
        accounts = []
        for _ in range(count):
            account = AccountFactory()
            response = self.client.post(BASE_URL, json=account.serialize())
            self.assertEqual(
                response.status_code,
                status.HTTP_201_CREATED,
                "Could not create test Account",
            )
            new_account = response.get_json()
            account.id = new_account["id"]
            accounts.append(account)
        return accounts

    ######################################################################
    #  A C C O U N T   T E S T   C A S E S
    ######################################################################

    def test_index(self):
        """It should get 200_OK from the Home Page"""
        response = self.client.get("/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_cors_security(self):
        """It should return a CORS header"""
        response = self.client.get('/', environ_overrides=HTTPS_ENVIRON)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.headers.get("Access-Control-Allow-Origin"), "*")

    def test_security_headers(self):
        """It should return security headers"""
        response = self.client.get('/', environ_overrides=HTTPS_ENVIRON)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        headers = {
            'X-Frame-Options': 'SAMEORIGIN',
            'X-XSS-Protection': '1; mode=block',
            'X-Content-Type-Options': 'nosniff',
            'Content-Security-Policy': 'default-src \'self\'; object-src \'none\'',
            'Referrer-Policy': 'strict-origin-when-cross-origin'
        }
        for key, value in headers.items():
            self.assertEqual(response.headers.get(key), value)

    def test_health(self):
        """It should be healthy"""
        resp = self.client.get("/health")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data["status"], "OK")

    def test_create_account(self):
        """It should Create a new Account"""
        account = AccountFactory()
        response = self.client.post(
            BASE_URL,
            json=account.serialize(),
            content_type="application/json"
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # Make sure location header is set
        location = response.headers.get("Location", None)
        self.assertIsNotNone(location)

        # Check the data is correct
        new_account = response.get_json()
        self.assertEqual(new_account["name"], account.name)
        self.assertEqual(new_account["email"], account.email)
        self.assertEqual(new_account["address"], account.address)
        self.assertEqual(new_account["phone_number"], account.phone_number)
        self.assertEqual(new_account["date_joined"], str(account.date_joined))

    def test_create_account_with_no_date(self):
        """It should Create a new Account without a date"""
        account = AccountFactory().serialize()
        del account["date_joined"]
        response = self.client.post(
            BASE_URL,
            json=account,
            content_type="application/json"
        )
        new_account = response.get_json()
        self.assertNotEqual(new_account["date_joined"], None)

    def test_bad_request(self):
        """It should not Create an Account when sending the wrong data"""
        response = self.client.post(BASE_URL, json={"name": "not enough data"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_unsupported_media_type(self):
        """It should not Create an Account when sending the wrong media type"""
        account = AccountFactory()
        response = self.client.post(
            BASE_URL,
            json=account.serialize(),
            content_type="test/html"
        )
        self.assertEqual(response.status_code, status.HTTP_415_UNSUPPORTED_MEDIA_TYPE)

    # Tests for list_accounts

    def test_list_no_accounts(self):
        """It should return an empty List when there are no Accounts"""
        response = self.client.get(
            BASE_URL
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.get_json(), [])

    def test_list_accounts(self):
        """ It should List all Accounts"""
        NUM_ACCOUNTS = 5
        self._create_accounts(NUM_ACCOUNTS)

        response = self.client.get(BASE_URL)
        data = response.get_json()

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(data), NUM_ACCOUNTS)

    # Tests for read_accounts

    def test_read_account(self):
        """ It should Read the correct Account """
        account = AccountFactory()
        response = self.client.post(
            BASE_URL,
            json=account.serialize(),
            content_type="application/json"
        )

        # Make sure location header is set
        location = response.headers.get("Location", None)
        self.assertIsNotNone(location)

        # Check the data is correct
        userid = response.get_json()["id"]
        result = self.client.get(f"{BASE_URL}/{userid}").get_json()
        self.assertEqual(result["name"], account.name)

    def test_read_nonexistent_account(self):
        """ It should not Read an Account that doesn't exist """
        response = self.client.get(
            f"{BASE_URL}/1", content_type="application/json"
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    # Tests for update_accounts

    def test_update_account(self):
        """ It should Update an Account """
        NUM_ACCOUNTS = 1
        orig_account_info = self._create_accounts(NUM_ACCOUNTS)[0]
        # update account 0 with account 1 data
        new_account_info = AccountFactory()
        account_id = orig_account_info.id

        response = self.client.put(
            f"{BASE_URL}/{account_id}",
            json=new_account_info.serialize(),
            content_type="application/json"
        )
        updated_account_info = response.get_json()
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(updated_account_info["name"], new_account_info.name)

    def test_update_no_account(self):
        """ It should not error when we Update a non Account """
        account_id = 0
        new_account_info = AccountFactory()
        response = self.client.put(
            f"{BASE_URL}/{account_id}",
            json=new_account_info.serialize(),
            content_type="application/json"
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_update_idempotency(self):
        """It should be idempotent when we Update the same Account"""
        account_id = self._create_accounts(1)[0].id
        new_account_info = AccountFactory()
        for _ in range(5):
            response = self.client.put(
                f"{BASE_URL}/{account_id}",
                json=new_account_info.serialize(),
                content_type="application/json"
            )
            updated_account_info = response.get_json()
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertEqual(updated_account_info["name"], new_account_info.name)

    def test_update_bad_request(self):
        """It should not Update an Account when sending the wrong data"""
        account_id = self._create_accounts(1)[0].id
        response = self.client.put(f"{BASE_URL}/{account_id}", json={"name": "not enough data"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_update_unsupported_media_type(self):
        """It should not Update an Account when sending the wrong media type"""
        account_id = self._create_accounts(1)[0].id
        new_account = AccountFactory()
        response = self.client.put(
            f"{BASE_URL}/{account_id}",
            json=new_account.serialize(),
            content_type="test/html"
        )
        self.assertEqual(response.status_code, status.HTTP_415_UNSUPPORTED_MEDIA_TYPE)

    # Tests for delete_accounts
    def test_delete_accounts(self):
        """It should Delete an Account"""
        account_id = self._create_accounts(1)[0].id
        response = self.client.delete(
            f"{BASE_URL}/{account_id}"
        )
        removed = self.client.get(
            f"{BASE_URL}/{account_id}"
        )

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(removed.status_code, status.HTTP_404_NOT_FOUND)

    def test_delete_non_account(self):
        """It should not error when we Delete non-Account"""
        account_id = 0
        # make sure the account doesn't exist
        not_found = self.client.get(
            f"{BASE_URL}/{account_id}"
        )
        self.assertEqual(not_found.status_code, status.HTTP_404_NOT_FOUND)

        # make sure we get the response we want
        response = self.client.delete(
            f"{BASE_URL}/{account_id}"
        )
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    def test_delete_idempotency(self):
        """It should be idempotent when we Delete the same Account"""
        account_id = self._create_accounts(1)[0].id
        for _ in range(5):
            response = self.client.delete(
                f"{BASE_URL}/{account_id}"
            )
            removed = self.client.get(
                f"{BASE_URL}/{account_id}"
            )
            self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
            self.assertEqual(removed.status_code, status.HTTP_404_NOT_FOUND)

    # Tests for Error Handlers
    def test_unsupported_method(self):
        """It should catch errors for bad methods"""
        response = self.client.patch(
            BASE_URL
        )
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_no_endpoint(self):
        """It should catch errors for resources not found"""
        response = self.client.get(
            f"{BASE_URL}/this-doesnt-exist"
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
