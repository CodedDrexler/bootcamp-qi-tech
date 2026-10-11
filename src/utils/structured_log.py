import json

from utils.logger import get_logger


logger = get_logger("ops")


def emit_event(event: str, level: str = "info", **fields) -> None:
    """Emite evento operacional estruturado sem decidir destino/retencao.

    Quem chama escolhe explicitamente os campos seguros. Nao passe payloads
    inteiros, CPF, nome, INTERNAL-TOKEN ou qualquer segredo.
    """
    payload = {"event": event, **fields}
    message = "EVENT " + json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    log_method = getattr(logger, level, logger.info)
    log_method(message)
