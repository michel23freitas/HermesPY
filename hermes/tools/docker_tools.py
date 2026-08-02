"""Ferramentas Docker: containers, logs, stats, networks, volumes."""

from hermes.tools.system_tools import run_cmd


def tool_docker_ps():
    """Lista containers Docker com status."""
    out = run_cmd("docker ps -a --format '{{.Names}}|{{.Status}}'")
    lines = []
    for l in out.splitlines():
        if "|" not in l:
            continue
        name, status = l.split("|", 1)
        if "Up" in status:
            lines.append(f"✅ {name} (até {status.split('(')[0].replace('Up ', '').strip()})")
        else:
            time_part = status.replace("Exited", "").replace("(", "").replace(")", "").strip()
            lines.append(f"⚠️ {name} ({time_part})")
    return "\n".join(lines) if lines else "Nenhum container."


def tool_docker_logs(container, lines=50):
    return run_cmd(f"docker logs --tail {lines} {container} 2>&1")


def tool_docker_stats():
    return run_cmd("docker stats --no-stream --format 'table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}'")


def tool_docker_restart(c):
    return run_cmd(f"docker restart {c}", timeout=60)


def tool_docker_stop(c):
    return run_cmd(f"docker stop {c}", timeout=60)


def tool_docker_start(c):
    return run_cmd(f"docker start {c}", timeout=60)


def tool_docker_inspect(container):
    result = run_cmd(
        f"docker inspect {container} --format 'Imagem: {{{{.Config.Image}}}}\\nStatus: {{{{.State.Status}}}}\\nNetwork: {{{{.HostConfig.NetworkMode}}}}\\nRestart: {{{{.HostConfig.RestartPolicy.Name}}}}' 2>&1"
    )
    volumes = run_cmd(f"docker inspect {container} --format '{{{{range .Mounts}}}}{{{{.Source}}}} -> {{{{.Destination}}}}\\n{{{{end}}}}'")
    ports = run_cmd(f"docker inspect {container} --format '{{{{range $k,$v := .NetworkSettings.Ports}}}}{{{{$k}}}}\\n{{{{end}}}}'")
    return f"{result}\n\nVolumes:\n{volumes}\nPortas:\n{ports}"


def tool_docker_networks():
    return run_cmd("docker network ls --format '{{.Name}}|{{.Driver}}'")


def tool_docker_volumes():
    return run_cmd("docker volume ls --format '{{.Name}}' | xargs -I{} docker volume inspect {} --format '{{.Name}}: {{.Mountpoint}}' 2>/dev/null")


def tool_docker_logsum(container, lines=60):
    """Resume erros críticos dos logs de um container usando IA."""
    logs = tool_docker_logs(container, lines)
    if not logs or "Sem saida" in logs:
        return "Nenhum log."
    prompt = f"Analise logs do container '{container}' e liste apenas erros criticos (max 5), em portugues:\n\n{logs}"
    try:
        from hermes.agent.loop import _get_ai_client
        from hermes.config import MODEL
        ai_client = _get_ai_client()
        resp = ai_client.chat.completions.create(
            model=MODEL, messages=[{"role": "user", "content": prompt}],
            temperature=0.2, max_tokens=400
        )
        return f"📋 Resumo logs ({container}):\n\n{resp.choices[0].message.content.strip()}"
    except Exception:
        return f"Erro ao resumir logs. Brutos:\n" + "\n".join(logs.splitlines()[-15:])
