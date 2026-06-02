import csv
import os
import logging
import unittest
from unittest import TestCase
from tempfile import TemporaryFile, mkdtemp
from multiprocessing import Process

from pandas.api.types import (
    is_datetime64_ns_dtype,
    is_float_dtype,
    is_int64_dtype,
    is_object_dtype,
)

from enverus_developer_api import (
    DeveloperAPIv3,
    DADatasetException,
    DAQueryException,
    DAAuthException,
)


LOG_LEVEL = logging.DEBUG

if os.environ.get("GITHUB_SHA"):
    LOG_LEVEL = logging.ERROR


# ------------------------------------------------------------
# V3 TOKEN SETUP
# ------------------------------------------------------------

def set_token_v3():
    """
    Creates DIRECTACCESSV3_TOKEN only if it does not already exist.
    Requires DIRECTACCESSV3_API_KEY to be set in PowerShell.
    """

    if os.environ.get("DIRECTACCESSV3_TOKEN"):
        return

    secret_key = os.environ.get("DIRECTACCESSV3_API_KEY")

    if not secret_key:
        raise RuntimeError(
            "Missing DIRECTACCESSV3_API_KEY.\n\n"
            "Set it first in PowerShell:\n"
            '$env:DIRECTACCESSV3_API_KEY="your_key_here"'
        )

    os.environ["DIRECTACCESSV3_TOKEN"] = DeveloperAPIv3(
        secret_key=secret_key,
        log_level=LOG_LEVEL,
        # url="https://api.dev.enverus.com/"
    ).access_token


def create_developerapi_v3():
    """
    Creates a DeveloperAPIv3 client using the secret key and saved token.
    """

    secret_key = os.environ.get("DIRECTACCESSV3_API_KEY")

    if not secret_key:
        raise RuntimeError(
            "Missing DIRECTACCESSV3_API_KEY.\n\n"
            "Set it first in PowerShell:\n"
            '$env:DIRECTACCESSV3_API_KEY="your_key_here"'
        )

    return DeveloperAPIv3(
        secret_key=secret_key,
        access_token=os.environ.get("DIRECTACCESSV3_TOKEN"),
        retries=5,
        backoff_factor=10,
        log_level=LOG_LEVEL,
        # url="https://api.dev.enverus.com/"
    )


def proc_query(dataset):
    """
    Used by multiprocessing test.
    Each process creates its own API client.
    """

    v3 = create_developerapi_v3()
    response = v3.query(dataset, deleteddate="null")
    first_row = next(response)

    assert first_row is not None


# ------------------------------------------------------------
# TESTS
# ------------------------------------------------------------

class TestEnverusDeveloperAPI(TestCase):

    @classmethod
    def setUpClass(cls) -> None:
        """
        Runs once before all tests.
        Only sets up V3.
        """

        set_token_v3()
        cls.v3 = create_developerapi_v3()

    # --------------------------------------------------------
    # AUTH TESTS
    # --------------------------------------------------------

    def test_missing_secret_key_v3(self):
        with self.assertRaises(DAAuthException):
            DeveloperAPIv3(secret_key=None, log_level=LOG_LEVEL)

    def test_token_refresh_v3(self):
        """
        Starts with a fake token.
        The API should refresh it automatically.
        """

        v3 = DeveloperAPIv3(
            secret_key=os.environ.get("DIRECTACCESSV3_API_KEY"),
            access_token="invalid",
            retries=5,
            backoff_factor=10,
            log_level=LOG_LEVEL,
        )

        invalid_token = v3.access_token

        count = v3.count("rigs", deleteddate="null")

        query = v3.query(
            "rigs",
            pagesize=10000,
            deleteddate="null",
        )

        records = list(query)

        self.assertEqual(len(records), count)
        self.assertNotEqual(invalid_token, v3.access_token)

    # --------------------------------------------------------
    # QUERY TESTS
    # --------------------------------------------------------

    def test_query_v3(self):
        query = self.v3.query(
            "casings",
            pagesize=10,
            deleteddate="null",
        )

        records = []

        for i, row in enumerate(query, start=1):
            records.append(row)

            if i >= 30:
                break

        self.assertTrue(
            len(records) > 0,
            "test_query_v3 records list empty",
        )

    def test_query_v3_omit_header_next_link(self):
        query = self.v3.query(
            "casings",
            pagesize=10,
            deleteddate="null",
            _headers={"X-Omit-Header-Next-Links": "true"},
        )

        records = []

        for i, row in enumerate(query, start=1):
            records.append(row)

            if i >= 30:
                break

        self.assertTrue(
            len(records) > 0,
            "test_query_v3_omit_header_next_link records list empty",
        )

    def test_count_v3(self):
        count = self.v3.count(
            "wells",
            updateddate="ge(2021-05-01)",
            StateProvince="in(TX,LA,WY)",
        )

        self.assertIsNotNone(count)
        self.assertIsInstance(count, int)

    # def test_count_invalid_dataset_v3(self):
    #     with self.assertRaises(DADatasetException):
    #         self.v3.count("invalid")

    # --------------------------------------------------------
    # HEADER / LINK TESTS
    # --------------------------------------------------------

    def test_is_omit_header_next_link(self):
        is_omit_next_link = self.v3.is_omit_header_next_link(
            _headers={"X-Omit-Header-Next-Links": "true"}
        )

        self.assertTrue(
            is_omit_next_link,
            "Should detect X-Omit-Header-Next-Links header",
        )

        is_omit_next_link = self.v3.is_omit_header_next_link(
            _headers={"Omit-Header-Next-Links": "true"}
        )

        self.assertFalse(
            is_omit_next_link,
            "Should not detect invalid omit header",
        )

    def test_parse_links(self):
        links = self.v3.parse_links(
            {
                "next": "</economics?action=next&next_page=WellID+%3C+840600005436298&pagesize=50>; rel='next'"
            }
        )

        self.assertTrue(links["next"]["url"])

    # --------------------------------------------------------
    # DOCS / DDL TESTS
    # --------------------------------------------------------

    def test_docs_v3(self):
        docs = self.v3.docs("casings")

        self.assertTrue(docs)
        self.assertIsInstance(docs, list)

    def test_ddl_v3(self):
        ddl = self.v3.ddl(
            "casings",
            database="pg",
        )

        with TemporaryFile(mode="w+") as file:
            file.write(ddl)
            file.seek(0)

            first_line = file.readline()

        self.assertTrue(
            first_line.startswith("CREATE TABLE casings"),
            "DDL should start with CREATE TABLE casings",
        )

    def test_ddl_invalid_db_v3(self):
        with self.assertRaises(DAQueryException):
            self.v3.ddl(
                "casings",
                database="invalid",
            )

    # --------------------------------------------------------
    # CSV TEST
    # --------------------------------------------------------

    def test_csv_v3(self):
        tempdir = mkdtemp()
        path = os.path.join(tempdir, "rigs.csv")

        dataset = "rigs"

        options = {
            "pagesize": 10000,
            "deleteddate": "null",
        }

        count = self.v3.count(dataset, **options)
        query = self.v3.query(dataset, **options)

        self.v3.to_csv(
            query,
            path,
            log_progress=True,
            delimiter=",",
            quoting=csv.QUOTE_MINIMAL,
        )

        with open(path, mode="r", newline="") as file:
            reader = csv.reader(file)
            row_count = len(list(reader))

        # +1 because CSV includes header row
        self.assertEqual(row_count, count + 1)

    # --------------------------------------------------------
    # DATAFRAME TEST
    # --------------------------------------------------------

def test_dataframe_v3(self):
    df = self.v3.to_dataframe(
        "rigs",
        pagesize=1000,
        deleteddate="null",
    )

    # Check index is set to API endpoint primary keys
    self.assertListEqual(
        df.index.names,
        ["CompletionID", "WellID"],
    )

    # Check object dtypes
    self.assertTrue(is_object_dtype(df.API_UWI))
    self.assertTrue(is_object_dtype(df.ActiveStatus))

    # Check datetime64 dtypes
    # DeletedDate may be all null because we queried deleteddate="null",
    # so do not require it to be datetime.
    self.assertTrue(is_datetime64_ns_dtype(df.SpudDate))
    self.assertTrue(is_datetime64_ns_dtype(df.UpdatedDate))

    # Check DeletedDate column exists, but allow object dtype if it is all null
    self.assertIn("DeletedDate", df.columns)

    # Check Int64 dtypes
    self.assertTrue(is_int64_dtype(df.RatedWaterDepth))
    self.assertTrue(is_int64_dtype(df.RatedHP))

    # Check float dtypes
    self.assertTrue(is_float_dtype(df.RigLatitudeWGS84))
    self.assertTrue(is_float_dtype(df.RigLongitudeWGS84))

    
    # --------------------------------------------------------
    # MULTIPROCESS TEST
    # --------------------------------------------------------

    def test_multiple_processes_v3(self):
        procs = [
            Process(target=proc_query, kwargs={"dataset": "rigs"}),
            Process(target=proc_query, kwargs={"dataset": "casings"}),
        ]

        for proc in procs:
            proc.start()

        for proc in procs:
            proc.join()

        for proc in procs:
            self.assertEqual(proc.exitcode, 0)

    # --------------------------------------------------------
    # CONTEXT MANAGER TEST
    # --------------------------------------------------------

    def test_enter_exit(self):
        with DeveloperAPIv3(
            secret_key=os.environ.get("DIRECTACCESSV3_API_KEY"),
            access_token=os.environ.get("DIRECTACCESSV3_TOKEN"),
            log_level=LOG_LEVEL,
        ) as api:
            self.assertIsInstance(api, DeveloperAPIv3)
            self.assertIsNotNone(api.session)

        self.assertIsNone(api.session)


if __name__ == "__main__":
    unittest.main()


