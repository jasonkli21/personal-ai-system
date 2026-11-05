"""One-generation fixture responder and a deterministic check, without I/O."""

from .reasoning_contracts import Answer, Arm, Task


def direct(task: Task) -> Answer:
    """Use only prepared inputs. Unknown or conflicting facts lead to abstention."""
    match task.family:
        case "numeric":
            # The deliberately simple fake uses addition for every numeric prompt.
            return Answer(value=str(sum(task.numbers)))
        case "planning":
            chosen = max(task.records, key=lambda r: len(set(r.tags) & set(task.constraints)))
            return Answer(value=chosen.value)
        case "citations" | "uncertainty" | "scope":
            facts = tuple(record for record in task.records if task.operation in record.tags)
            values = {record.value for record in facts}
            if len(values) == 1:
                return Answer(value=values.pop(), citations=tuple(record.key for record in facts))
            return Answer()
        case _:
            return Answer(
                value=next(
                    (record.value for record in task.records if record.key == task.operation),
                    None,
                )
            )


def verify(task: Task, arm: Arm, answer: Answer) -> bool:
    """Check only the preregistered numeric diagnostic using bounded arithmetic."""
    if arm != "direct_plus_check" or task.family != "numeric":
        raise ValueError("unsupported_check")
    if task.operation == "sum":
        total = 0
        for number in task.numbers:
            total += number
    elif task.operation == "product":
        total = 1
        for number in task.numbers:
            total *= number
    else:
        raise ValueError("unsupported_operation")
    return answer.value == str(total)
