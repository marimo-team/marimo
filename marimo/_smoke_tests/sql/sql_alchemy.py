import marimo

__generated_with = "0.15.5"
app = marimo.App()


@app.cell(hide_code=True)
def _(mo):
    mo.md("""# SQLAlchemy Demo""")
    return


@app.cell
def _():
    import marimo as mo
    return (mo,)


@app.cell
def _():
    import sqlalchemy as sa
    from sqlalchemy.orm import declarative_base, Session
    from sqlalchemy.orm import Mapped, mapped_column
    import polars as pl
    return Mapped, Session, declarative_base, mapped_column, pl, sa


@app.cell
def _(Mapped, declarative_base, mapped_column, sa):
    # Create an in-memory SQLite database
    engine = sa.create_engine("sqlite:///:memory:")

    # Define our models
    Base = declarative_base()


    class User(Base):
        __tablename__ = "users"

        id: Mapped[int] = mapped_column(primary_key=True)
        name: Mapped[str] = mapped_column(sa.String(50))
        age: Mapped[int] = mapped_column(sa.Integer)


    # Create tables
    Base.metadata.create_all(engine)
    return User, engine


@app.cell
def _(Session, User, engine):
    # Insert sample data
    with Session(engine) as _session:
        users = [
            User(name="Alice", age=25),
            User(name="Bob", age=30),
            User(name="Charlie", age=35),
            User(name="Diana", age=28),
        ]
        _session.add_all(users)
        _session.commit()
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md("""### All Users""")
    return


@app.cell
def _(Session, User, engine, mo, pl):
    # Query examples
    with Session(engine) as _session:
        # Basic query
        all_users = _session.query(User).all()
        df = pl.DataFrame(
            [(u.name, u.age) for u in all_users],
            schema=["Name", "Age"],
            orient="row",
        )

    mo.hstack(
        [
            df,
            mo.vstack(
                [
                    mo.md("### Stats"),
                    f"Average age: {df['Age'].mean():.1f}",
                    f"Total users: {len(df)}",
                ]
            ),
        ]
    )
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md("""### Users under 30 (ordered by name)""")
    return


@app.cell
def _(Session, User, engine, mo):
    # Advanced queries
    with Session(engine) as _session:
        # Filter and order
        young_users = (
            _session.query(User).filter(User.age < 30).order_by(User.name).all()
        )

    mo.ui.table(
        [{"Name": u.name, "Age": u.age} for u in young_users], selection=None
    )
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md("""### Age Statistics""")
    return


@app.cell
def _(Session, User, engine, sa):
    # Aggregation example
    with Session(engine) as _session:
        age_stats = _session.query(
            sa.func.count(User.id).label("count"),
            sa.func.avg(User.age).label("avg_age"),
            sa.func.min(User.age).label("min_age"),
            sa.func.max(User.age).label("max_age"),
        ).one()

    [
        ("Total Users", age_stats.count),
        ("Average Age", f"{age_stats.avg_age:.1f}"),
        ("Youngest", age_stats.min_age),
        ("Oldest", age_stats.max_age),
    ]
    return


if __name__ == "__main__":
    app.run()
