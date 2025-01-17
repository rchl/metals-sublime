from .. commands.lsp_metals_text_command import LspMetalsTextCommand
from functools import reduce, partial
from LSP.plugin.core.css import css
from LSP.plugin.core.protocol import Range
from LSP.plugin.core.sessions import Session
from LSP.plugin.core.typing import Any, List, Dict, Optional, Union
from LSP.plugin.core.views import range_to_region, FORMAT_MARKED_STRING, FORMAT_MARKUP_CONTENT, minihtml

import mdpopups
import sublime
import sublime_plugin


class WorksheetListener(sublime_plugin.ViewEventListener):
    def on_modified(self) -> None:
        file_name = self.view.file_name()
        if file_name and file_name.endswith('.worksheet.sc'):
            self.view.run_command('lsp_metals_clear_phantoms')

class LspMetalsClearPhantomsCommand(LspMetalsTextCommand):
    def run(self, edit: sublime.Edit) -> None:
        fname = self.view.file_name()
        if not fname:
            return
        sublime.set_timeout_async(partial(self.run_async, fname))

    def run_async(self, fname: str) -> None:
        session = self.session_by_name()
        if not session:
            return
        handle_decorations(session, fname)

def handle_decorations(session: Session, params: Union[Dict[str, Any], str]) -> None:
    phantom_key = "metals_decoraction"
    field_name = "_lsp_metals_decorations"
    clear_phantoms = False
    uri = None
    if isinstance(params, str):
        uri = session.config.map_client_path_to_server_uri(params)
        clear_phantoms = True
    elif isinstance(params, dict):
        uri = params.get('uri')

    if not uri:
        return

    session_buffer = session.get_session_buffer_for_uri_async(uri)
    if not session_buffer:
        return
    session_view = next(iter(session_buffer.session_views), None)
    if session_view:
        phantoms = []
        try:
            phantom_set = getattr(session_buffer, field_name)
        except AttributeError:
            phantom_set = sublime.PhantomSet(session_view.view, phantom_key)
            setattr(session_buffer, field_name, phantom_set)

        if not clear_phantoms:
            phantoms = decorations_to_phantom(params.get('options', []), session_view.view)

        phantom_set.update(phantoms)

PHANTOM_HTML = """
<style>div.phantom {{font-style: italic; color: {}}}</style>
<div class='phantom'>{}{}</div>"""

def show_popup(content: Dict[str, Any], view: sublime.View, location: int) -> None:
    html = minihtml(view, content, allowed_formats=FORMAT_MARKED_STRING | FORMAT_MARKUP_CONTENT)
    viewport_width = view.viewport_extent()[0]
    mdpopups.show_popup(
        view,
        html,
        css=css().popups,
        md=False,
        flags=sublime.HIDE_ON_MOUSE_MOVE_AWAY,
        location=location,
        wrapper_class=css().popups_classname,
        max_width=viewport_width,
        on_navigate=None)


def decoration_to_phantom(option: Dict[str, Any], view: sublime.View) -> Optional[sublime.Phantom]:
    decoration_range = Range.from_lsp(option['range'])
    region = range_to_region(decoration_range, view)
    region.a = region.b  # make the start point equal to the end point
    hoverMessage = deep_get(option, 'hoverMessage')
    contentText = deep_get(option, 'renderOptions', 'after', 'contentText')
    link = ''
    point = view.text_point(decoration_range.start.row, decoration_range.start.col)
    if hoverMessage:
        link = " <a href='more'>more</a>"

    color = view.style_for_scope("comment")["foreground"]
    phantom_content = PHANTOM_HTML.format(color, contentText, link)
    phantom = sublime.Phantom(
        region,
        phantom_content,
        sublime.LAYOUT_INLINE,
        lambda href: show_popup(hoverMessage, view, point))

    return phantom

def decorations_to_phantom(options: Dict[str, Any], view: sublime.View) -> List[sublime.Phantom]:
    return map(lambda o: decoration_to_phantom(o, view), options)

def deep_get(dictionary: Dict[str, Any], *keys):
    return reduce(lambda d, key: d.get(key) if d else None, keys, dictionary)
