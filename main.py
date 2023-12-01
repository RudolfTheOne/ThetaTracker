from datetime import datetime, timedelta
import urwid
from config_setup import load_user_config, load_system_config, save_user_config, read_tickers
from config_setup import validate_max_delta, validate_dte_range_min, validate_dte_range_max, \
    validate_buying_power
from data_fetch import is_market_open, fetch_option_chain
import logging

def format_option(option):
    if "message" in option:
        row1 = urwid.Text([('default', f"\n")])
        row2 = urwid.Text([('default', option["message"])])
        row3 = urwid.Text([('default', f"\n")])
        return urwid.Pile([row1, row2, row3])

    if option['put_call_ratio'] > 1.1:
        put_call_emoji = '⚠️ '
    elif option['put_call_ratio'] < 0.9:
        put_call_emoji = '✅ '
    else:
        put_call_emoji = '⚖️ '

    row1 = urwid.Text([
        ('default', f"\nTicker: "),
        ('bright white', f"{option['ticker']} [{option['line_number']}], "),
        ('default', f"Premium Total: "),
        ('bright green,bold', f"${option['premium_usd']}, "),
        ('default', f"(per day: ${option['premium_per_day']}), "),
        ('default', f"ARR: "),
        ('bright white', f"{option['arr']}%, "),
        ('bright cyan', f"LIQ.: "),
        ('default', f"BidSize: "),
        ('dark green', f"{option['bidSize']}, "),
        ('default', f"AskSize: "),
        ('dark green', f"{option['askSize']}, "),
        ('default', f"Spread: "),
        ('bright green,bold', f"{round(((option['ask'] - option['bid']) / option['ask']) * 100, 2)}%")
    ])

    row2 = urwid.Text([
        ('dark red', f"   RISK: "),
        ('default', f"PUT/CALL ratio: "),
        ('bright white', f"{round(option['put_call_ratio'],2)} {put_call_emoji}, "),
        ('default', f"Stock IV: "),
        ('bright white', f"{option['underlying_iv']}, "),
        ('default', f"Delta: "),
        ('bright white', f"{option['delta']}, "),
        ('default', f"Underlying price: $"),
        ('dark green', f"{round(option['underlyingPrice'], 2)} "),
        ('bright white',
         f"(d: ${round(option['underlyingPrice'] - option['strikePrice'], 2)} "
         f"{round((option['underlyingPrice'] - option['strikePrice']) / option['underlyingPrice'], 2)}%), ")
    ])

    row3 = urwid.Text([
        ('bright white', f"   TRADE: "),
        ('bright white,bold', f"{option['description']}, "),
        ('default', f"Strike Price: "),
        ('bright white', f"${option['strikePrice']}, "),
        ('default', f"DTE: "),
        ('bright white', f"{option['daysToExpiration']}, "),
        ('default', f"No to open: "),
        ('bright purple', f"{option['no_of_contracts_to_write']} @ ${option['bid']}"),
        ('default', " ⚠️  📆") if option["has_earnings"] else ('default', '')
    ])

    return urwid.Pile([row1, row2, row3])

class SortingOptions(urwid.WidgetWrap):
    def __init__(self, options, select_callback):
        self.select_callback = select_callback

        # Create a button for each option and wrap it in a Filler widget
        buttons = [urwid.Filler(urwid.Button(option, on_press=self.select_option))
                   for option in options]

        # Create a pile with the buttons
        pile = urwid.Pile(buttons)

        # Call the parent constructor with the pile
        super().__init__(pile)

    def select_option(self, button):
        # This function is called when a button is pressed
        self.select_callback(button.label)

class MainFrame(urwid.Frame):
    def __init__(self, main_area, footer, user_config, system_config, tickers, loop=None):

        self.main_area = main_area
        self.user_config = user_config
        self.system_config = system_config
        self.tickers = tickers
        self.loop = loop
        self.current_sorting_method = user_config["default_sorting_method"] if user_config else "arr"
        self.filter_earnings = False
        self.fetched_options = []

        # Create header_text and main_area here
        self.header_text = urwid.Text([
            ("header-bold", "ThetaTracker"),
            ("header", " - "),
            ("header", "Date: "), ("header-bold", datetime.now().strftime("%Y-%m-%d %H:%M")),
            ("header", ", "),
            ("header", "Buying Power: "), ("header-bold", f"${user_config['buying_power']}"),
            ("header", ", "),
            ("header", "Market: "), ("header-bold", "Open" if is_market_open(system_config["api_key"]) else "Closed")
        ])
        header = urwid.AttrMap(self.header_text, "header")
        super().__init__(self.main_area, header=header, footer=footer)
        # Dictionary to store the validation functions
        self.validation_functions = {
            "max_delta": validate_max_delta,
            "dte_range_min": validate_dte_range_min,
            "dte_range_max": validate_dte_range_max,
            "buying_power": validate_buying_power
        }

    def select_sorting_option(self, option):
        # This function is called when a sorting option is selected
        self.current_sorting_method = option
        self.user_config["default_sorting_method"] = option
        footer_text = urwid.Text([
            "q: exit app, c: configuration setup, s: sort by (now: {} desc.), r: forced refresh".format(
                self.current_sorting_method)
        ])
        footer_text = urwid.AttrMap(footer_text, "footer")
        self.footer.original_widget = footer_text

        # logging.debug(f'Sorting option changed to: {option}')

        # Create a copy of the user config and remove unwanted fields
        user_config_to_save = self.user_config.copy()
        user_config_to_save['max_delta'] = float(user_config_to_save['max_delta'])
        user_config_to_save['dte_range_min'] = int(user_config_to_save['dte_range_min'])
        user_config_to_save['dte_range_max'] = int(user_config_to_save['dte_range_max'])
        user_config_to_save['buying_power'] = float(user_config_to_save['buying_power'])
        user_config_to_save['default_sorting_method'] = str(user_config_to_save['default_sorting_method'])
        user_config_to_save.pop('from_date', None)
        user_config_to_save.pop('to_date', None)

        save_user_config(user_config_to_save)

        self.refresh_data(self.tickers, self.user_config["from_date"], self.user_config["to_date"], option)

    def create_sorting_widget(self):
        # Create a list of sorting options
        sorting_options = ["arr", "premium_usd", "premium_per_day", "delta"]

        # Create a SortingOptions widget
        sorting_options_widget = SortingOptions(sorting_options, self.select_sorting_option)

        # Add a frame around the SortingOptions widget
        framed_widget = urwid.LineBox(sorting_options_widget, title="Select Sorting Option")

        # Create an Overlay widget with the SortingOptions widget on top of the current body
        overlay = urwid.Overlay(framed_widget, self.body,
                                align='center', width=('relative', 20),
                                valign='middle', height=('relative', 10),
                                min_width=20, min_height=9, top=-20)

        # Return the created widget
        return overlay
    def keypress(self, size, key):
        if key == 'esc':
            # Handle 'esc' key event here, restore the main window.
            if isinstance(self.body, urwid.Overlay):
                self.body = self.body[0]
            else:
                return super().keypress(size, key)
        elif key == 'q':
            raise urwid.ExitMainLoop()
        elif key == 'c':
            # Create a list of configuration options
            configuration_options = ["max_delta", "dte_range_min", "dte_range_max", "buying_power"]

            # Create a ConfigurationOptions widget
            configuration_options_widget = ConfigurationOptions(configuration_options, self.select_configuration_option, self, self.user_config)

            # Add a frame around the ConfigurationOptions widget
            framed_widget = urwid.LineBox(configuration_options_widget, title="Edit User Configuration")

            # Create an Overlay widget with the ConfigurationOptions widget on top of the current body
            overlay = urwid.Overlay(framed_widget, self.body,
                                    align='center', width=('relative', 20),
                                    valign='middle', height=('relative', 10),
                                    min_width=20, min_height=9, top=-20)

            # Set the Overlay widget as the body of the frame
            self.body = overlay
        elif key == 's':
            self.body = self.create_sorting_widget()
        elif key == 'r':
            self.refresh_data(self.tickers, self.user_config["from_date"], self.user_config["to_date"])
        elif key == 'e':
            self.filter_earnings = not self.filter_earnings
            self.refresh_display()
        else:
            return super().keypress(size, key)

    def close_config_setup(self):
        # Switch back to the main screen
        self.set_body(self.main_area)

    def refresh_data(self, tickers, from_date, to_date, sorting_method="arr"):
        self.fetched_options = fetch_option_chain(
            self.system_config["api_key"],
            tickers,
            from_date,  # from_date passed as argument
            to_date,  # to_date passed as argument
            self.user_config["max_delta"],
            self.user_config["buying_power"],  # buying_power from user_config
            sorting_method,
            self.system_config["finnhub_api_key"]
            )
        self.refresh_display()

    def refresh_display(self):
        displayed_options = [option for option in self.fetched_options if
                             not (self.filter_earnings and option["has_earnings"])]

        options_list = urwid.SimpleListWalker(
            [format_option(option) for option in displayed_options] + [urwid.Divider('-')]
        )
        self.main_area = urwid.ListBox(options_list)
        self.main_area = urwid.Pile([self.main_area])
        self.refresh_header()

        self.body = self.main_area
        if self.loop is not None:
            self.loop.draw_screen()

    def refresh_header(self):
        self.header_text.set_text([
            ("header-bold", "ThetaTracker"),
            ("header", " - "),
            ("header", "Date: "), ("header-bold", datetime.now().strftime("%Y-%m-%d %H:%M")),
            ("header", ", "),
            ("header", "Buying Power: "), ("header-bold", f"${self.user_config['buying_power']}"),
            ("header", ", "),
            ("header", "Market: "), ("header-bold", "Open" if is_market_open(self.system_config["api_key"]) else "Closed")
        ])

    def apply_config(self, new_config, tickers):
        # Update the user_config
        self.user_config = new_config
        self.tickers = tickers

        # Recalculate from_date and to_date
        from_date = datetime.now() + timedelta(new_config["dte_range_min"])
        to_date = datetime.now() + timedelta(new_config["dte_range_max"])

        new_config["from_date"] = from_date
        new_config["to_date"] = to_date

        # Fetch new options
        options = fetch_option_chain(
            self.system_config["api_key"],
            self.tickers,
            from_date,
            to_date,
            new_config["max_delta"],
            new_config["buying_power"],
            new_config["default_sorting_method"],
            self.system_config["finnhub_api_key"]
        )

        # Update the options list
        options_list = urwid.SimpleListWalker(
            [format_option(option) for option in options] + [urwid.Divider('-')]
        )
        self.main_area = urwid.ListBox(options_list)
        self.main_area = urwid.Pile([self.main_area])
        self.body = self.main_area  # If main_area is indeed the body

        # Update the footer text
        footer_text = urwid.Text([
            "q: exit app, c: configuration setup, s: sort by (now: {} desc.), e: filter out stocks with earnings, r: forced refresh".format(
                new_config["default_sorting_method"])
        ])
        self.footer = urwid.AttrMap(footer_text, "footer")
        if self.loop is not None:
            self.loop.draw_screen()

    def select_configuration_option(self, option, edit_widget):
        # Update the selected configuration option with the new value
        if isinstance(edit_widget, urwid.ListBox):
            # For ListBox, get the label of the item in focus
            new_value = edit_widget.focus.get_label()
        elif isinstance(edit_widget, urwid.LineBox):
            # Get the original widget inside the LineBox
            original_widget = edit_widget.original_widget
            if isinstance(original_widget, urwid.Edit):
                new_value = original_widget.get_edit_text()
            elif isinstance(original_widget, urwid.ListBox):
                # For ListBox, get the label of the item in focus
                new_value = original_widget.focus.get_label()
        else:
            new_value = edit_widget.get_edit_text()

        # Validate the new value only for specified options
        if option in ["max_delta", "dte_range_min", "dte_range_max", "buying_power"]:
            validate_func = self.validation_functions[option]

            if option == "dte_range_max":
                dte_range_min = self.user_config["dte_range_min"]
                is_valid, error_message = validate_func(dte_range_min, new_value)
                if not is_valid:
                    self.show_error_message(error_message)
                    return
            else:
                is_valid, error_message = validate_func(new_value)
                if not is_valid:
                    self.show_error_message(error_message)
                    return

        # If the new value is valid, update the user config and save it
        self.user_config[option] = new_value

        # Create a copy of the user config and remove unwanted fields
        user_config_to_save = self.user_config.copy()
        user_config_to_save['max_delta'] = float(user_config_to_save['max_delta'])
        user_config_to_save['dte_range_min'] = int(user_config_to_save['dte_range_min'])
        user_config_to_save['dte_range_max'] = int(user_config_to_save['dte_range_max'])
        user_config_to_save['buying_power'] = float(user_config_to_save['buying_power'])
        user_config_to_save.pop('from_date', None)
        user_config_to_save.pop('to_date', None)

        save_user_config(user_config_to_save)

        # Update the footer text
        footer_text = urwid.Text([
            "q: exit app, c: configuration setup, s: sort by (now: {} desc.), r: forced refresh".format(
                user_config_to_save["default_sorting_method"])
        ])
        self.footer = urwid.AttrMap(footer_text, "footer")
        if self.loop is not None:
            self.loop.draw_screen()

        # Return to the main window
        self.body = self.body[0]

    def refresh_content(self, loop, user_data):
        from_date = user_data['from_date']  # get from user_data
        to_date = user_data['to_date']  # get from user_data
        tickers = user_data['tickers']
        self.refresh_data(tickers, from_date, to_date)
        # Set another alarm. The same user_data will be used again.
        loop.set_alarm_in(self.system_config['refresh_interval'], self.refresh_content, user_data=user_data)

    def show_error_message(self, error_message):
        # Create a new text widget with the error message
        error_text = urwid.Text(error_message)

        # Wrap the text widget in an AttrMap to apply the 'error' style
        error_widget = urwid.AttrMap(error_text, 'error')

        # Replace the footer with the error widget
        self.footer = error_widget

        # Draw the screen to show the changes
        if self.loop is not None:
            self.loop.draw_screen()

class ConfigSetup(urwid.WidgetWrap):
    def __init__(self, user_config, close_callback):
        self.user_config = user_config
        self.close_callback = close_callback

        # Create input fields for each configuration value
        self.max_delta_input = urwid.Edit(edit_text=str(self.user_config["max_delta"]))
        self.max_delta_input = urwid.Columns([('fixed', 14, urwid.Text("Maximum Delta: ")), self.max_delta_input])

        self.dte_range_min_input = urwid.Edit(edit_text=str(self.user_config["dte_range_min"]))
        self.dte_range_min_input = urwid.Columns(
            [('fixed', 14, urwid.Text("DTE range min.: ")), self.dte_range_min_input])

        self.dte_range_max_input = urwid.Edit(edit_text=str(self.user_config["dte_range_max"]))
        self.dte_range_max_input = urwid.Columns(
            [('fixed', 14, urwid.Text("DTE range max.: ")), self.dte_range_max_input])

        self.buying_power_input = urwid.Edit(edit_text=str(self.user_config["buying_power"]))
        self.buying_power_input = urwid.Columns([('fixed', 14, urwid.Text("Buying power: ")), self.buying_power_input])

        self.sorting_method_input = urwid.Edit(edit_text=self.user_config["default_sorting_method"])
        self.sorting_method_input = urwid.Columns(
            [('fixed', 14, urwid.Text("Sorting method: ")), self.sorting_method_input])

        # Create a button for saving the configuration
        save_button = urwid.Button("Save", on_press=self.save_config)

        self.error_message = urwid.Text("")

        # Create a pile with the input fields and the save button
        pile = urwid.Pile([
            self.max_delta_input,
            self.dte_range_min_input,
            self.dte_range_max_input,
            self.buying_power_input,
            self.sorting_method_input,
            save_button
        ])

        # Call the parent constructor with the pile
        super().__init__(urwid.Filler(pile))

    def save_config(self, button):
        # Read the new configuration values from the input fields
        max_delta = self.max_delta_input.contents[1][0].get_edit_text()
        dte_range_min = self.dte_range_min_input.contents[1][0].get_edit_text()
        dte_range_max = self.dte_range_max_input.contents[1][0].get_edit_text()
        buying_power = self.buying_power_input.contents[1][0].get_edit_text()
        sorting_method = self.sorting_method_input.contents[1][0].get_edit_text()
        # Validate the new configuration values
        try:
            max_delta = float(max_delta)
            dte_range_min = int(dte_range_min)
            dte_range_max = int(dte_range_max)
            buying_power = float(buying_power)
        except ValueError:
            self.error_message.set_text("Invalid input: Delta range, DTE range, and buying power must be numbers.")
            return

        # Check if sorting_method is a valid value
        valid_sorting_methods = ["premium_usd", "premium_per_day", "delta", "arr"]
        if sorting_method not in valid_sorting_methods:
            # The sorting method is not valid
            self.error_message.set_text("Invalid input: Sorting method must be one of: " + ", ".join(valid_sorting_methods))
            return

        # Save the new configuration values to the user configuration file
        self.user_config["max_delta"] = float(max_delta)
        self.user_config["dte_range_min"] = int(dte_range_min)
        self.user_config["dte_range_max"] = int(dte_range_max)
        self.user_config["buying_power"] = float(buying_power)
        self.user_config["default_sorting_method"] = sorting_method

        # Save the user configuration to a file
        try:
            ConfigSetup.save_config(self.user_config)
        except RuntimeError:
            self.error_message.set_text("An error occurred while trying to save the configuration.")
            return

        self.close_callback()

class ConfigurationOptions(urwid.ListBox):
    def __init__(self, options, callback, main_frame, user_config):
        self.callback = callback
        self.options = options
        self.main_frame = main_frame
        self.user_config = user_config
        self.selected_option = None
        self.current_sorting_method = "arr"

        # Create list of button widgets and corresponding edit widgets
        self.option_widgets = []
        for option in options:
            button = urwid.AttrMap(urwid.Button(option, on_press=self.on_option_selected), None, 'reversed')
            if option == "default_sorting_method":
                # Use a ListBox for the "default_sorting_method" option
                listbox = main_frame.create_sorting_widget()
                widget = (button, listbox)
            else:
                widget = (button, urwid.Edit(caption='', edit_text=str(self.user_config[option])))
            self.option_widgets.append(widget)

        # Call ListBox constructor with SimpleFocusListWalker
        super().__init__(urwid.SimpleFocusListWalker([widget[0] for widget in self.option_widgets]))

    def on_option_selected(self, button):
        # Find the corresponding edit widget
        edit_widget = None
        for widget in self.option_widgets:
            if widget[0].base_widget == button:
                self.selected_option = widget[0].base_widget.get_label()  # Save selected option
                edit_widget = widget[1]
                break

        # Set the body of the ListBox directly to the edit widget
        self.body = urwid.SimpleFocusListWalker([edit_widget])

    def keypress(self, size, key):
        key = super().keypress(size, key)
        # If 'enter' is pressed, call the callback with the selected option
        if key == 'enter':
            # Instead of creating a new widget, get the current one which has the user's input
            edit_widget = self.focus
            self.callback(self.selected_option, edit_widget)
        else:
            return key

def main():
    file_path = "./tickers2watch.txt"
    # Load the user and system configurations
    system_config = load_system_config()
    user_config = load_user_config()
    tickers = read_tickers(file_path)

    logging.basicConfig(filename='debug.log', level=logging.WARNING)

    # Check if the market is open
    is_open = is_market_open(system_config["api_key"])
    if not is_open:
        print("The market is currently closed.")

    from_date = datetime.now() + timedelta(days=user_config["dte_range_min"])
    to_date = datetime.now() + timedelta(days=user_config["dte_range_max"])

    user_config["from_date"] = from_date
    user_config["to_date"] = to_date

    print("Loading options...")
    options = fetch_option_chain(system_config["api_key"], tickers, from_date, to_date,
                                 user_config["max_delta"], user_config["buying_power"],
                                 user_config["default_sorting_method"], system_config["finnhub_api_key"])

    palette = [
        ("header", "white", "dark red"),
        ("header-bold", "white,bold", "dark red"),
        ("footer", "white", "dark blue"),
        ('bright white', 'white', ''),
        ('dark green', 'dark green', ''),
        ('dark red', 'dark red', ''),
        ('blue', 'dark blue', ''),
        ('bright purple', 'dark magenta', ''),
        ('bright green,bold', 'light green', ''),
        ('bright white,bold', 'white', ''),
        ('bright cyan', 'light cyan', ''),
        ("error", "white", "dark red"),
    ]

    # Create the main area
    options_list = urwid.SimpleListWalker(
        [format_option(option) for option in options] + [urwid.Divider('-')]
    )
    main_area = urwid.ListBox(options_list)
    main_area = urwid.Pile([main_area])

    footer_text = urwid.Text([
        "q: exit app, c: configuration setup, s: sort by (now: {} desc.), r: forced refresh".format(user_config["default_sorting_method"])
    ])
    footer = urwid.AttrMap(footer_text, "footer")

    # Create the layout
    layout = MainFrame(main_area, footer=footer, user_config=user_config, system_config=system_config, tickers=tickers)
    layout.fetched_options = options
    loop = urwid.MainLoop(layout, palette=palette)
    layout.loop = loop

    loop.set_alarm_in(
        system_config['refresh_interval'],
        layout.refresh_content,
        user_data={'from_date': from_date, 'to_date': to_date, 'tickers': tickers}
    )

    config = load_user_config()

    # If the config was not loaded, show user config widget
    if not config:
        layout.show_user_config_widget(loop, save_user_config)
    else:
        loop.set_alarm_in(0, lambda loop, _: layout.apply_config(user_config, tickers))
    # Run the main loop
    loop.run()

if __name__ == "__main__":
    main()