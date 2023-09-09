# AutoPin app specification

## Message event handler

+ message_listener("on_message")
+ on_raw_message_edit

|Condition |        |            |          |           |OUTPUT |       | |
|:---:     |:---:      |:---:       |:---:     |:---:      |:---:  |:---:  |:---  |
|isBot     |KEY_WORD   |KEY_REACTION</br> to cue|REACTION</br> to post |HISTORY(post)    |App.   |History|Comment|
|||||||||
|Yes       |-          |-           |-         |-          |-      |-      |Bot    |
|No        |No         |-           |-         |exist      |unpin  |delete |Keyword Deleted|
|^         |^          |^           |^         |not exist  |-      |-      |Nominal Message|
|^         |Yes        |Yes         |-         |exist      |unpin  |delete |*unusual case but exist|
|^         |^          |^           |-         |not exist  |-      |-      |edit unpinned message|
|^         |^          |No          |No        |exist      |unseal |-      |edit pinned message|
|^         |^          |^           |^         |not exist  |pin    |add    |pin new message|
|^         |^          |^           |Yes       |exist      |seal   |-      |edit sealed message|
|^         |^          |^           |^         |~~not exist~~  |~~seal~~   |~~add~~    |non exist case|

```plantuml
!pragma useVerticalIf on
start
if (isBot?) then (Yes)
  stop
else(No)
  :fetch History of (cue) Message;
if (History exist?) then (Yes)
  :fetch pinned message;
else(No)
endif
if (No KEYWORD in Message?) then (Yes)
    if(History exist?) then (No)
      stop
    else(Yes)
      :App    : Unpin(no KEYWORD);
      stop
    endif
(No)elseif (KEYREACTION to Message?) then (Yes)
    if(History exist?) then (No)
      stop
    else(Yes)
      :App    : Unpin(KEYREACTION);
      stop
    endif
(No)elseif (History exist?) then (Yes)
    if(No REACTION to pinned Message?) then (No)
      :App    : Seal;
      stop
    else(Yes)
      :App    : Unseal;
      stop
    endif
else(No)
  :App    : pinToChannel;
endif
stop
```

## Reaction Event Handler

+ on_raw_reaction_add

|Condition            |             |       |        |                |OUTPUT  |
|:---:                |:---:        |:---:  |:---:   |:---:           |:---:   |
|History(post/cue)    | Post or Cue | emoji | user   | # of reactions |Action  |
|                     |             |       |        |                |        |
|not exist            |-            |-      |-       |-               |-       |
|exist                |post         |-      |-       | # = 1          |Seal    |
|^                    |^            |^      |^       | # > 2          |-       |
|^                    |cue          |=check |=author | -              |unpin   |
|^                    |cue          |=check |!=author| -              |-       |
|^                    |other        |-      |-       |-               |-       |

```plantuml
!pragma useVerticalIf on
start
:fetch History of (post/cue) Message;
if (History exist?) then (No)
  stop
else(Yes)
endif
if (Post?) then (No (cue))
  if (emoji=check?) then (No)
    stop
  else(Yes)
  endif
  if (user=Author?) then (No)
    stop
  else(Yes)
  endif
  :unpin;
  stop
else(Yes(post))
:fetch Message;
if ( # of Reactions=1) then (No)
  stop
else(Yes)
:Seal;
stop
```

+ on_raw_reaction_remove
+ on_raw_reaction_clear
+ on_raw_reaction_clear_emoji

|Condition        |             |        |                   |             |OUTPUT  |
|:---:            |:---:        |:---:   |:---:              |:---:        |:---:   |
|History(post)    | Post or Cue | emoji  | # of reactions    | Keyword     |Action  |
|                 |             |        |                   |             |        |
|exist            | Post        | -      | # = 0             | -           | unseal |
|^                | ^           | ^      | # > 1             | -           | -      |
|^                | Cue         | -      | -                 | -           | -      |
|not exist        | -           | !=check| -                 | -           | -      |
|^                | ^           | =check or unknown | #CheckReaction >1 | -           | -      |
|^                | ^           | ^      | #CheckReaction =0 | in contents | pinToChannel |
|^                | ^           | ^      | ^                 | No          | -      |

```plantuml
!pragma useVerticalIf off
start
:fetch History of (post/cue) Message;
if (History of post exist?) then (Yes)
:fetch post Message;
if ( # of Reaction = 0?) then (No)
  stop
else(Yes)
:unseal;
endif
stop
(No) elseif (History of cue exist?) then (Yes)
  stop  
else(No)
  if (EVENT TYPE = reaction_clear?) then (No)
    if (emoji=check?) then (No)
      stop
    else (Yes)
    endif
  else(Yes)
  endif
  :fetch reacted Message;
  if ( # of Check Reaction = 0?) then (No)
    stop
  else (Yes)
  endif
  if ( KEYWORD in contents? ) then (No)
    stop
  else (Yes)
  :pinToChannel;
  endif
  stop
```
