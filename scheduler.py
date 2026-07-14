import time
import threading
import db
import checker

def check_traps_loop(bot):
    """
    Background loop that runs in a thread and checks active nick traps.
    """
    print("Trap checker background thread started.")
    while True:
        try:
            active_traps = db.get_active_traps()
            if active_traps:
                print(f"Trap checker: Checking {len(active_traps)} active traps...")
                for trap in active_traps:
                    trap_id = trap['id']
                    user_id = trap['user_id']
                    username = trap['username']
                    
                    print(f"Trap checker: Verifying @{username}...")
                    available = checker.is_username_available(username)
                    
                    if available is True:
                        print(f"Trap checker: Username @{username} is FREE! Notifying user {user_id}.")
                        try:
                            message_text = (
                                f"🔔 <b>Ловушка сработала!</b>\n\n"
                                f"Юзернейм <b>@{username}</b> освободился и доступен!\n"
                                f"Успейте занять его в Telegram или Fragment!"
                            )
                            bot.send_message(user_id, message_text, parse_mode="HTML")
                            # Deactivate the trap now that it's triggered
                            db.deactivate_trap(trap_id)
                        except Exception as e:
                            print(f"Error sending trap notification to {user_id}: {e}")
                            
                    elif available is False:
                        print(f"Trap checker: Username @{username} is still occupied.")
                        
                    else:
                        print(f"Trap checker: Error checking @{username} (likely rate limit/network). Skipping.")
                        d
                    # Delay between individual checks to avoid rate limits
                    time.sleep(3.0)
                    
            # Sleep between full sweep cycles (e.g. 5 minutes)
            # In production, this can be 10-15 minutes. For testing, we make it 2 minutes.
            time.sleep(120.0)
        except Exception as e:
            print(f"Error in trap checker loop: {e}")
            time.sleep(30.0) # sleep on error and retry

def start_scheduler(bot):
    """
    Starts the trap checker in a background thread.
    """
    thread = threading.Thread(target=check_traps_loop, args=(bot,), daemon=True)
    thread.start()
    return thread
