from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
import multiprocessing
import time

import pytest

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from desk_kernel.invoice_allocation import reserve_invoice_amount


def _reserve_in_worker(url):
    engine = create_engine(url)
    with Session(engine) as db:
        with reserve_invoice_amount(db):
            taken = set(db.execute(text("SELECT amount FROM reservations")).scalars())
            amount = next(value for value in range(1, 100) if value not in taken)
            time.sleep(0.005)  # hold the read/write race open across independent workers
            db.execute(text("INSERT INTO reservations (amount) VALUES (:amount)"), {"amount": amount})
            db.commit()
            return amount


@pytest.mark.parametrize("processes", [False, True])
def test_amount_selection_and_insert_are_atomic_across_separate_connections(tmp_path, processes):
    url = f"sqlite:///{tmp_path / 'concurrent.sqlite3'}"
    engine = create_engine(url)
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE reservations (amount INTEGER PRIMARY KEY)"))

    options = {"mp_context": multiprocessing.get_context("spawn")} if processes else {}
    executor_type = ProcessPoolExecutor if processes else ThreadPoolExecutor
    with executor_type(max_workers=4, **options) as executor:
        amounts = list(executor.map(_reserve_in_worker, [url] * 24))
    assert len(amounts) == len(set(amounts)) == 24
