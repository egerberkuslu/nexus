def check_ryu():
    """
    Returns (installed: bool, version: str|None)
    """
    try:
        import ryu
        version = getattr(ryu, "__version__", None)
        print(f"Ryu is installed. Version: {version or 'unknown'}")
        return True, version
    except ModuleNotFoundError:
        print("Ryu is NOT installed.")
        return False, None

if __name__ == "__main__":
    check_ryu()
