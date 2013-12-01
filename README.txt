Guild Wars 2 DPS meter.

gw2dps meter calculates the damage per second taken by the selected targeted. It does this by periodically 
sampling the target's health and appling a timed running average. This app does not modify the guild wars 2 client,
it only reads process memory. It is written in python using tkinter, and it is just like any other regulard window 
program. See requirements to get it do display ontop of guild wars. 

If multiple players are attacking the same takrget the DPS displayed will be a sum of the DPS of all the players.
This occurins because it meausre the DPS taken by a target. To measure your own personal DPS, make sure you ware 
the only one attacking your target. 

As of v0.5-alpha, there are two DPS values displayes.

Instant:
  DPS calculated over 1 second. This is done by acquiring 4 samples at 250ms, then summed up. The sample window is then
  moved by 250ms. So the displayed value is actually for the previous 1s.
  
Sustained:
  Same as instant but done over 5 seconds. 
  
Note: 
  If you lick on the app, it will take mouse and keyboard focus away from the game, so position it somehwere you won't
  accidently press on it. I like to place at the top of the window where the target's health bar appears. 
  
Features:
  - Max values are displayed in RED for 5seconds when they occur. Damage is still being calculated so if a new max occrus
    it will be updated and displayed for 5 more seconds. 
  
  - When the character leaves combat, both Instant and Sustained DPS will be displayed in ORANGE. This is the Instand and
    Susstainted averages during the time the character has been in combat
  
  - Mouseover the Instant/Sustained frame will display a new frame underneath to give a summary of the values. 
    Red values are the maxes, oragange are the averages from the last time the character was in combat. These 
    values are always beeing updated if they change
    
  - Can measure party/guild/group DPS
  
REQUIREMENTS:

  - This is a tkinter app given the parameter to be a toplevel window (always displayed on top), but to be able to 
    display it on top of Guild Wars 2, the guild wars 2 needs be either in "Windowed" mode or "Windowed Fullscreen",
    oterwise DX takes over and this app will never be ontop. 
  
  - The "autotargeting" feature in guild wars 2 should be enabled. This is a "soft" requirment and if it is not enable, 
    you need to manually select the target before attacking it. 

  
WARNNING:

  This program reads guild wars 2 process memory to get the target health. This may be viewed as illegal based on the
  guild wars 2 agreement. I take no responsability if a ban occur because of htis app
  
  Personally i think getting banned for using this is exteremely unlikely, so use at your own discretion. 
