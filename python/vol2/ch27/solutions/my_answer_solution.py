"""Reference answer to the practical task of chapter 27."""


def ce_of_class(result, name):
    for row in result["credit_enhancement"]:
        if row["class"] == name:
            return f"{row['credit_enhancement']:.3%}"
    return None
