# WooCommerce to Apple Numbers Automation

A Python-based order management automation developed for a small e-commerce business.

## Overview

The project integrates the WooCommerce REST API with Apple Numbers to reduce manual order administration.

## Features

- Retrieve orders from WooCommerce
- Import eligible GBP orders into Apple Numbers
- Prevent duplicate order imports
- Organise orders into monthly tables
- Check and backfill missing payment fees
- Run scheduled automation tasks on macOS

## Technologies

Python, WooCommerce REST API, AppleScript, Apple Numbers, macOS launchd.

## Security

API credentials are loaded from environment variables. Customer data, spreadsheets and credentials are excluded from version control.

## Status

Test automation implemented. Deployment configuration and further reliability testing are ongoing.
