import re
import jinja2
import os
from app.settings import settings


def render_template(template_name: str, data: dict = None) -> str:
    if data is None:
        data = {}
    template = _get_template_env().get_template(template_name)
    rendered = template.render(**data).replace("\n", " ")
    rendered = rendered.replace("<br>", "%0A")
    rendered = re.sub(" +", " ", rendered).replace(" .", ".").replace(" ,", ",")
    rendered = "%0A".join(line.strip() for line in rendered.split("%0A"))
    rendered = rendered.replace("{FOURPACES}", "    ")
    return rendered


def _get_template_env():
    if not getattr(_get_template_env, "template_env", None):
        template_loader = jinja2.FileSystemLoader(searchpath=settings.templates_dir)
        env = jinja2.Environment(
            loader=template_loader,
            trim_blocks=True,
            lstrip_blocks=True,
            autoescape=True,
        )

        _get_template_env.template_env = env

    return _get_template_env.template_env
