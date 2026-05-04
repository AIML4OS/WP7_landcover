from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedSeq, CommentedMap

def update_yaml_config(input_file_path, output_file_path, updates_dict):
    """
    Updates a YAML configuration file by merging updates_dict into the existing structure.
    Preserves formatting: inline for simple lists, block for nested ones.
    """
    yaml = YAML()
    yaml.preserve_quotes = True
    yaml.default_flow_style = False 
    yaml.indent(mapping=2, sequence=4, offset=2)

    with open(input_file_path, 'r') as f:
        data = yaml.load(f)

    def format_value(value):
        """Helper to format lists as flow (inline) or block based on content."""
        if isinstance(value, list):
            # If it's a simple list (no nested dicts/lists), use flow style [1, 2, 3]
            if all(not isinstance(i, (dict, list)) for i in value):
                cs = CommentedSeq(value)
                cs.fa.set_flow_style()
                return cs
            else:
                return CommentedSeq([format_value(i) for i in value])
        elif isinstance(value, dict):
            cm = CommentedMap()
            for k, v in value.items():
                cm[k] = format_value(v)
            return cm
        return value

    def recursive_update(target, updates):
        """Recursively update a dict-like structure instead of overwriting."""
        for key, value in updates.items():
            if isinstance(value, dict) and key in target and isinstance(target[key], dict):
                recursive_update(target[key], value)
            else:
                # Apply the specific formatting before assignment
                target[key] = format_value(value)

    # 1. Update data recursively instead of simple assignment
    recursive_update(data, updates_dict)
    
    # 2. Save the result
    with open(output_file_path, 'w') as f:
        yaml.dump(data, f)

