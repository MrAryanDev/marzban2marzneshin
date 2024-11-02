# One Command Migrate Tool!

A fast tool to migrate from **Marzban** to **Marzneshin** in **Just One Step**:


## Run The Script:

to run the script and migrate; run this command.
```bash
sudo bash -c "$(curl -sL https://raw.githubusercontent.com/MrAryanDev/marzban2marzneshin/master/run.sh)" @ --run
```
after now you can access the marzban2marzneshin script with just type `marzban2marzneshin` in your terminal.

## Script:
after install or run the migrate script you can see the help of script with this command. 
```bash
marzban2marzneshin --help
```


## Notes:
> Stop The Updating Source Service Before Install Or Update The Marzneshin Panel with `systemctl stop marzban2marzneshin`; Restart This Service After Install Or Update the Marzneshin Panel with `systemct start marzban2marzneshin`

> This script receives the important data of the border guard panel and transfers them to the border guard panel of the **same server**

> Due to the difference between Marzban and Marzneshin subscription routing, this script adds a service to add Marzban subscription routing to Marzban subscription routes, so that you can use your Marzban subscriptions in case of Marzneshin update

> In all the stages of writing the codes, it has been tried to make the script compatible with the next updates of both panels by default, but if an incompatible update is applied from the side of the panels, this script is also updated and you can use the `marzban2marzneshin --update` command to update the new one.

> Our intention is not to disrespect the hard work of anyone. This project is designed for individuals who, for any reason, need to migrate. I appreciate the efforts of both the Marzban and Marzneshin teams and wish them success. 🤝

> I thank [@ErfJabs](https://github.com/erfjab) for creating the first migration project; He and his codes helped me a lot✨

## Contact & Support

- Telegram Channel: [@ErfJabs](https://t.me/MrAryanDevChan)

Feel free to ⭐ the project to show your support!

[![Stargazers over time](https://starchart.cc/MrAryanDev/marzban2marzneshin.svg?variant=adaptive)](https://starchart.cc/MrAryanDev/marzban2marzneshin)