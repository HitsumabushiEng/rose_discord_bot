# table

|Condition |        |            |          |           |OUTPUT |       | |
|:---:     |:---:      |:---:       |:---:     |:---:      |:---:  |:---:  |:---  |
|isBot     |KEY_WORD   |KEY_REACTION</br> to cue|REACTION</br> to post |HISTORY(post)    |App.   |History|Comment|
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
  :fetch History of Message;
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
