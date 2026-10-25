from concurrent.futures import ThreadPoolExecutor

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from desk_kernel.invoice_allocation import reserve_invoice_amount


def test_amount_selection_and_insert_are_atomic_across_separate_connections(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'concurrent.sqlite3'}")
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE reservations (amount INTEGER PRIMARY KEY)"))

    def reserve(_):
        with Session(engine) as db:
            with reserve_invoice_amount(db):
                taken = set(db.execute(text("SELECT amount FROM reservations")).scalars())
                amount = next(value for value in range(1, 100) if value not in taken)
                db.execute(text("INSERT INTO reservations (amount) VALUES (:amount)"), {"amount": amount})
                db.commit()
                return amount

    with ThreadPoolExecutor(max_workers=8) as executor:
        amounts = list(executor.map(reserve, range(24)))
    assert len(amounts) == len(set(amounts)) == 24
