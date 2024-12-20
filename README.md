<h1 style="text-align: center;">Marzban -> Marzneshin</h1>

<p style="text-align: center;">
    A tool to convert Marzban to Marzneshin
</p>


<p style="text-align: center;">
    <a href="https://t.me/MrAryanDevChan" target="_blank">
        <img src="https://img.shields.io/badge/telegram-channel-blue?style=flat-square&logo=telegram" alt="Telegram"/>
    </a>
    <a href="#">
        <img src="https://img.shields.io/github/stars/MrAryanDev/marzban2marzneshin?style=social" alt="GitHub Stars" />
    </a>
</p>

## Table of Contents

- [Features](#features)
- [Docs](#docs)
  - [Export](#export)
  - [Import](#import)

# Features

- Move **Admins**:
    - username
    - password
    - create datetime
    - sudo status
    - password reset datetime
- Move **Users**(Each **user's** transfer is done to their **admin**, and each **admin** has access to their own **users**):
    - username
    - **VLESS or VMESS** uuid(Clients that the user has in the Marzban panel will **not be disconnected**)
    - status(enable/disable)
    - used traffic
    - lifetime used traffic
    - traffic reset datetime
    - node usages
    - data limit
    - data limit reset strategy
    - expire strategy
    - expire datetime
    - usage duration(on hold expire duration)
    - activation deadline(on hold timeout)
    - last sub update datetime
    - create datetime
    - note
    - last online datetime
    - last edit datetime
- Move **Node Usages**:
    - full info of all nodes usages
- Move **System Data Usage**:
    - system uplink
    - system downlink
- Border Guard users can access their subscriptions even **without changing the port**.
- Ability to transfer and synchronize multiple Border Guard panels into one Border Guard panel **without changing users and their subscriptions**.
- Determining different behaviors in different situations by the user.
- Superfast.

# Docs

## Export
1- Run the following command in marzban server

```bash
sudo bash -c "$(curl -sL https://github.com/MrAryanDev/marzban2marzneshin/raw/master/run.sh)"
```
Enter `1` to enter the extraction section.

2- Enter the preferred protocol.
> **Note**: Currently, only vless or vmess protocol transmission is possible.
- **vless**: Using vless protocol uuids is preferred.
> If the vless protocol is not found for a user, the program automatically tries to use the vmess protocol.

- **vmess**: Using vmess protocol uuids is preferred.
> If the vmess protocol is not found for a user, the program automatically tries to use the vless protocol.

3- Enter behavior for non-uuid users.
> **Note**: Some users may not use either the vless or vmess protocols.

- **revoke**: Create a new uuid for that user.

- **skip**: Do not transfer that user.

Now the extracted data is located at `/root/marzban2marzneshin.db`

## import
(First of all, upload the file you received from the export step to the marzneshin server [e.g: /root/marzban2marzneshin.db])

1- Run the following command in marzneshin server

```bash
sudo bash -c "$(curl -sL https://github.com/MrAryanDev/marzban2marzneshin/raw/master/run.sh)"
```
Enter `2` to enter the importation section.

2- Enter the path to the file exported in the first step.

3- Enter how to deal with existing admins.
- **raname**: Add a _ with 4 additional characters at the end of the username

- **update**: Update the same admin's information without changing the username.

- **skip**: This admin cannot be transferred.

4- Enter how to deal with existing users.
- **raname**: Add a _ with 4 additional characters at the end of the username

- **update**: Update the same user's information without changing the username.

- **skip**: This user cannot be transferred.

5- Enable marzban sub service: 
Run the following command in **marzneshin** server
```bash
sudo systemctl daemon-reload; sudo systemctl enable marzban2marzneshin; systemctl restart marzban2marzneshin
```

6- change AUTH_GENERATION_ALGORITHM:

- In **marzneshin**:
```bash
echo 'AUTH_GENERATION_ALGORITHM="plain"' | sudo tee -a /etc/opt/marzneshin/.env
sudo wget -qO /usr/local/bin/yq https://github.com/mikefarah/yq/releases/latest/download/yq_linux_amd64
sudo chmod +x /usr/local/bin/yq
yq eval '.services.marznode.environment.AUTH_GENERATION_ALGORITHM = "plain"' -i /etc/opt/marzneshin/docker-compose.yml
```
- In **marznode**:
  - if you are using env file:
```bash
echo 'AUTH_GENERATION_ALGORITHM="plain"' | sudo tee -a /path/to/marznode/.env
```
> **Note**: Replace `/path/to/marznode/.env` with the path to your **marznode** `.env` file.

  - if you are using docker compose file for environment variables:
```bash
sudo wget -qO /usr/local/bin/yq https://github.com/mikefarah/yq/releases/latest/download/yq_linux_amd64
sudo chmod +x /usr/local/bin/yq
yq eval '.services.marznode.environment.AUTH_GENERATION_ALGORITHM = "plain"' -i /path/to/marznode/docker-compose.yml
```
> **Note**: Replace `/path/to/marznode/docker-compose.yml` with the path to your **marznode** `docker-compose.yml` file.
> If you are using the Marznode document, the path of marznode docker compose file is `~/marznode/docker-compose.yml`.
> if you are using any tool for installing marznode, check the documents of that tool for find marznode docker compose file 

7- restart **marzneshin** and **marznode** services:
- **marzneshin**: `marzneshin restart`
- **marznode**: `docker compose -f /path/to/marznode/docker-compose.yml restart`
> **Note**: Replace `/path/to/marznode/docker-compose.yml` with the path to your **marznode** `docker-compose.yml` file.
> If you are using the Marznode document, the path of marznode docker compose file is `~/marznode/docker-compose.yml`.
> if you are using any tool for installing marznode, check the documents of that tool for find marznode docker compose file 

Feel free to ⭐ the project to show your support!

[![Stargazers over time](https://starchart.cc/MrAryanDev/marzban2marzneshin.svg?variant=adaptive)](https://starchart.cc/MrAryanDev/marzban2marzneshin)
