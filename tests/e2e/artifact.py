"""Read exported artifacts with standard readers independent of Forage."""

import csv
import json
import sqlite3
import sys

kind, path = sys.argv[1:]
if kind == "csv":
    with open(path, newline="", encoding="utf-8") as source:
        print(json.dumps(list(csv.DictReader(source)), ensure_ascii=False))
else:
    with sqlite3.connect(path) as database:
        database.row_factory = sqlite3.Row
        print(
            json.dumps(
                {
                    table: [
                        dict(row) for row in database.execute(f"SELECT * FROM {table}")
                    ]
                    for table in ("groups", "posts", "comments")
                }
            )
        )
