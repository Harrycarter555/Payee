short_url = context.user_data.get('short_url', '')

    if short_url:
        file_opener_url = f'https://t.me/{FILE_OPENER_BOT_USERNAME}?start={short_url}'
        post_to_channel(file_name, file_opener_url)
        update.message.reply_text('The link has been posted to the channel.')
    else:
        update.message.reply_text('No link to post. Please start over.')

    return ConversationHandler.END
