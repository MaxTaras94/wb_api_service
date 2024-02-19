def digit_separator(number: int) -> str:
	return "{:,}".format(number).replace(',', ' ')