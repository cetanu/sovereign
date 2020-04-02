# Terminology

## Source

The standard way of inputting data to Sovereign.

A Source should be a list of key:value mappings, which will be used in the process
of generating configuration for your envoy proxies to consume.

Sovereign has a few builtin Source types, one being `file` which can be a file either locally or over HTTP.
The other builtin Source type is `inline`, which has to be included in the main configuration file for Sovereign 
and is less dynamic (it can't easily be changed whereas a file/http source can).

## Instances

## Modifier

## Global Modifier

## Node

## Discovery Request

## Discovery Response

