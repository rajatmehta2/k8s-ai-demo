from app.kubernetes.pod_inspector import inspect_pods as real_inspect_pods

def inspect_pods():
    """
    Delegates to the real pod status inspector.
    """
    return real_inspect_pods()

