from fastapi import APIRouter, WebSocket, status
from starlette.responses import HTMLResponse

from auth import dependencies as auth_deps
from core import dependencies as core_deps
from core import schemas as core_schemas

from . import models, schemas, utils

chat_router: APIRouter = APIRouter(
    prefix="/chat",
    tags=["Chat"],
    responses={401: {"model": core_schemas.ResponseDetail}},
)


@chat_router.post("/create", status_code=status.HTTP_201_CREATED)
async def create_chat(
    chat_data: schemas.ChatInput,
    sql_session: core_deps.SqlSession,
    user: auth_deps.User,
) -> schemas.ChatDB:
    chat: models.Chat = await models.Chat(**chat_data.dict()).create(sql_session)
    user.chats.append(chat)
    await sql_session.commit()
    return schemas.ChatDB.from_orm(chat)


@chat_router.get("/{chat_id}")
async def get_chat_history(
    chat_id: str,
    sql_session: core_deps.SqlSession,
    no_sql_session: core_deps.NoSqlSession,
    user: auth_deps.User,
    skip: int,
    limit: int = 50,
) -> schemas.ChatHistory:
    return await utils.ChatHistoryMaker(user, chat_id, sql_session, no_sql_session, skip, limit).get()


@chat_router.websocket("/ws/{chat_id}")
async def websocket_manager(websocket: WebSocket):
    ...


@chat_router.get("/")
def index():
    return HTMLResponse(
        """<html>
<head>
<script src='http://ajax.googleapis.com/ajax/libs/jquery/1.11.0/jquery.min.js'></script>
<script>
$(document).ready(function(){
  if (typeof WebSocket != 'undefined') {
    $('#ask').show();
  } else {
    $('#error').show();
  }

  // join on enter
  $('#ask input').keydown(function(event) {
    if (event.keyCode == 13) {
      $('#ask a').click();
    }
  })

  // join on click
  $('#ask a').click(function() {
    join($('#ask input').val());
    $('#ask').hide();
    $('#channel').show();
    $('input#message').focus();
  });

  function join(name) {
    var host = window.location.host.split(':')[0];
    var ws = new WebSocket("{{ url_for('chatroom_ws') }}");

    var container = $('div#msgs');
    ws.onmessage = function(evt) {
      var obj = JSON.parse(evt.data);
      if (typeof obj != 'object') return;

      var action = obj['action'];
      var struct = container.find('li.' + action + ':first');
      if (struct.length < 1) {
        console.log("Could not handle: " + evt.data);
        return;
      }

      var msg = struct.clone();
      msg.find('.time').text((new Date()).toString("HH:mm:ss"));

      if (action == 'message') {
        var matches;
        if (matches = obj['message'].match(/me/)) {
          msg.find('.user').text(obj['user'] + ' ' + matches[1]);
          msg.find('.user').css('font-weight', 'bold');
        } else {
          msg.find('.user').text(obj['user']);
          msg.find('.message').text(': ' + obj['message']);
        }
      } else if (action == 'control') {
        msg.find('.user').text(obj['user']);
        msg.find('.message').text(obj['message']);
        msg.addClass('control');
      }

      if (obj['user'] == name) msg.find('.user').addClass('self');
      container.find('ul').append(msg.show());
      container.scrollTop(container.find('ul').innerHeight());
    }

    $('#channel form').submit(function(event) {
      event.preventDefault();
      var input = $(this).find(':input');
      var msg = input.val();
      if (msg) {
        ws.send(JSON.stringify({ action: 'message', user: name, message: msg }));
      }
      input.val('');
    });
  }
});
</script>
<style type="text/css" media="screen">
  * {
    font-family: Georgia;
  }
  a {
    color: #000;
    text-decoration: none;
  }
  a:hover {
    text-decoration: underline;
  }
  div.bordered {
    margin: 0 auto;
    margin-top: 100px;
    width: 600px;
    padding: 20px;
    text-align: center;
    border: 10px solid #ddd;
    -webkit-border-radius: 20px;
  }
  #error {
    background-color: #BA0000;
    color: #fff;
    font-weight: bold;
  }
  #ask {
    font-size: 20pt;
  }
  #ask input {
    font-size: 20pt;
    padding: 10px;
    margin: 0 10px;
  }
  #ask span.join {
    padding: 10px;
    background-color: #ddd;
    -webkit-border-radius: 10px;
  }
  #channel {
    margin-top: 100px;
    height: 480px;
    position: relative;
  }
  #channel div#descr {
    position: absolute;
    left: -10px;
    top: -190px;
    font-size: 13px;
    text-align: left;
    line-height: 20px;
    padding: 5px;
    width: 630px;
  }
  div#msgs {
    overflow-y: scroll;
    height: 400px;
  }
  div#msgs ul {
    list-style: none;
    padding: 0;
    margin: 0;
    text-align: left;
  }
  div#msgs li {
    line-height: 20px;
  }
  div#msgs li span.user {
    color: #ff9900;
  }
  div#msgs li span.user.self {
    color: #aa2211;
  }
  div#msgs li span.time {
    float: right;
    margin-right: 5px;
    color: #aaa;
    font-family: "Courier New";
    font-size: 12px;
  }
  div#msgs li.control {
    text-align: center;
  }
  div#msgs li.control span.message {
    color: #aaa;
  }
  div#input {
    text-align: left;
    margin-top: 20px;
  }
  div#input #message {
    width: 600px;
    border: 5px solid #bbb;
    -webkit-border-radius: 3px;
    font-size: 30pt;
  }
</style>
</head>
<body>
  <div id="error" class="bordered" style="display: none;">
    This browser has no native WebSocket support.<br/>
    Use a WebKit nightly or Google Chrome.
  </div>
  <div id="ask" class="bordered" style="display: none;">
    Name: <input type="text" id="name" /> <a href="#"><span class="join">Join!</span></a>
  </div>
  <div id="channel" class="bordered" style="display: none;">
    <div id="descr" class="bordered">
      <strong>Tip:</strong> Open up another browser window to chat.
    </div>
    <div id="msgs">
      <ul>
        <li class="message" style="display: none">
          <span class="user"></span><span class="message"></span>
          <span class="time"></span>
        </li>
      </ul>
    </div>
    <div id="input">
      <form><input type="text" id="message" /></form>
    </div>
  </div>
</body>
</html>"""
    )
