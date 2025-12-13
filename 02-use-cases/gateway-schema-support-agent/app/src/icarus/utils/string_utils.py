def preview_text(
    text: str, num_lines_start: int, num_lines_end: int = 0, show_line_nums: bool = False
) -> str:
    lines_original = text.split("\n")
    if show_line_nums:
        lines_original = [f"{i + 1}: {line}" for i, line in enumerate(lines_original)]

    num_lines_original = len(lines_original)
    num_lines_skipped = num_lines_original - (num_lines_start + num_lines_end)

    if not 0 <= num_lines_start <= num_lines_original:
        raise ValueError(f"num_lines_start must be between 0 and {num_lines_original}")

    if not 0 <= num_lines_end <= num_lines_original:
        raise ValueError(f"num_lines_end must be between 0 and {num_lines_original}")

    if num_lines_skipped < 0:
        raise ValueError(
            f"{num_lines_original} lines found, but "
            f"num_lines_start + num_lines_end = {num_lines_start + num_lines_end}"
        )

    if num_lines_skipped == 0:
        return text

    lines_skipped_text = f"... {num_lines_skipped} more lines skipped ..."
    lines_output = [*lines_original[:num_lines_start], lines_skipped_text]
    if num_lines_end > 0:
        lines_output += lines_original[-num_lines_end:]

    return "\n".join(lines_output)
