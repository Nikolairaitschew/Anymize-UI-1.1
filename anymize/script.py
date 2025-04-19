#!/usr/bin/env python3
import json
import json5
from faker import Faker

# Initialize Faker for the German locale.
fake = Faker('de_DE')

def generate_unique_names(n):
    """
    Generates n unique German first names using Faker.
    """
    unique_names = set()
    while len(unique_names) < n:
        unique_names.add(fake.first_name())
    return list(unique_names)

def replace_john_in_object(obj, names, index_tracker):
    """
    Recursively traverse the JSON object and replace any occurrence of 'john'
    with a name from the provided names list.
    """
    if isinstance(obj, dict):
        for key, value in obj.items():
            obj[key] = replace_john_in_object(value, names, index_tracker)
    elif isinstance(obj, list):
        for i in range(len(obj)):
            obj[i] = replace_john_in_object(obj[i], names, index_tracker)
    elif isinstance(obj, str):
        if obj == "john":
            new_name = names[index_tracker[0] % len(names)]
            index_tracker[0] += 1
            return new_name
    return obj

def main():
    # Generate a list of 1000 unique German first names.
    names = generate_unique_names(1000)

    input_file = "new_dataset.json"
    try:
        # Attempt to load as standard JSON first.
        with open(input_file, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError:
        # Fall back to json5 if standard JSON loading fails.
        with open(input_file, "r", encoding="utf-8") as f:
            data = json5.load(f)
    
    # Replace occurrences of "john" with names from our list.
    index_tracker = [0]
    data_modified = replace_john_in_object(data, names, index_tracker)

    output_file = "new_dataset_modified.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(data_modified, f, ensure_ascii=False, indent=4)

    print(f"Replacement completed. Modified file saved as {output_file}")

if __name__ == "__main__":
    main()
