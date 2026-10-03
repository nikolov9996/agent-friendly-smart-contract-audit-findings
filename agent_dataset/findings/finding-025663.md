---
id: 25663
severity: "Crit/High"
---

# Attacker can block LayerZero channel due to missing check of minimum gas passed

## Description



## Proof of Concept

**Layer Zero minimum gas showcase**

While sending messages through LayerZero, the sender can specify how much gas he is willing to give to the Relayer to deliver the payload to the destination chain. This configuration is specified in [relayer adapter params](<https://layerzero.gitbook.io/docs/evm-guides/advanced/relayer-adapter-parameters>). All the invocations of `lzSend` inside the TapiocaDao contracts naively assume that it is not possible to specify less than 200k gas on the destination, but in reality, you can pass whatever you want. As a showcase, I have set up a simple contract that implements the `NonBlockingLzApp` and sends only 30k gas which reverts on the destination chain resulting in `StoredPayload` and blocking of the message pathway between the two lzApps. The transaction below proves that if no minimum gas is enforced, an application that has the intention of using the `NonBlockingApp` can end up in a situation where there is a `StoredPayload` and the pathway is blocked.

Transaction Hashes for the example mentioned above:

- LayerZero Scan: [https://layerzeroscan.com/106/address/0xe6772d0b85756d1af98ddfc61c5339e10d1b6eff/message/109/address/0x5285413ea82ac98a220dd65405c91d735f4133d8/nonce/1](<https://layerzeroscan.com/106/address/0xe6772d0b85756d1af98ddfc61c5339e10d1b6eff/message/109/address/0x5285413ea82ac98a220dd65405c91d735f4133d8/nonce/1>)
- Tenderly stack trace of the sending transaction hash: [https://dashboard.tenderly.co/tx/avalanche-mainnet/0xe54894bd4d19c6b12f30280082fc5eb693d445bed15bb7ae84dfaa049ab5374d/debugger?trace=0.0.1](<https://dashboard.tenderly.co/tx/avalanche-mainnet/0xe54894bd4d19c6b12f30280082fc5eb693d445bed15bb7ae84dfaa049ab5374d/debugger?trace=0.0.1>)
- Tenderly stack trace of the receiving transaction hash: [https://dashboard.tenderly.co/tx/polygon/0x87573c24725c938c776c98d4c12eb15f6bacc2f9818e17063f1bfb25a00ecd0c/debugger?trace=0.2.1.3.0.0.0.0](<https://dashboard.tenderly.co/tx/polygon/0x87573c24725c938c776c98d4c12eb15f6bacc2f9818e17063f1bfb25a00ecd0c/debugger?trace=0.2.1.3.0.0.0.0>)

**Attack scenario**

The attacker calls [`triggerSendFrom`](<https://github.com/Tapioca-DAO/tapiocaz-audit/blob/master/contracts/tOFT/BaseTOFT.sol#L99>) and specifies a small amount of gas in the [airdropAdapterParams(\~50k gas)](<https://github.com/Tapioca-DAO/tapiocaz-audit/blob/master/contracts/tOFT/modules/BaseTOFTOptionsModule.sol#L41>). The Relayer delivers the transaction with the specified gas at the destination.

The transaction is first validated through the LayerZero contracts before it reaches the `lzReceive` function. The Relayer will give exactly the gas which was specified through the `airdropAdapterParams`. The line where it happens inside the LayerZero contract is [here](<https://github.com/LayerZero-Labs/LayerZero/blob/main/contracts/Endpoint.sol#L118>), and `{gas: _gasLimit}` is the gas the sender has paid for. The objective is that due to this small gas passed the transaction reverts somewhere inside the [`lzReceive`](<https://github.com/Tapioca-DAO/tapioca-sdk/blob/1eff367cd8660ecea4d5ed87184eb76c93791c96/src/contracts/lzApp/LzApp.sol#L36-L41>) function and the message pathway is blocked, resulting in [`StoredPayload`](<https://github.com/LayerZero-Labs/LayerZero/blob/main/contracts/Endpoint.sol#L122>).

The objective of the attack is that the execution doesn't reach the [`NonblockingLzApp`](<https://github.com/Tapioca-DAO/tapioca-sdk/blob/1eff367cd8660ecea4d5ed87184eb76c93791c96/src/contracts/lzApp/NonblockingLzApp.sol#L25>) since then the behavior of the `NonBlockingLzApp` would be as expected and the pathway wouldn't be blocked, but rather the message would be stored inside the [`failedMessages`](<https://github.com/Tapioca-DAO/tapioca-sdk/blob/1eff367cd8660ecea4d5ed87184eb76c93791c96/src/contracts/lzApp/NonblockingLzApp.sol#L18>)

## Recommendation

The minimum gas enforced to send for each and every `_lzSend` in the app should be enough to cover the worst-case scenario for the transaction to reach the first try/catch which is [here](<https://github.com/Tapioca-DAO/tapioca-sdk/blob/1eff367cd8660ecea4d5ed87184eb76c93791c96/src/contracts/lzApp/NonblockingLzApp.sol#L25>).

I would advise the team to do extensive testing so this min gas is enforced.

Immediate fixes:

1. This is most easily fixed by overriding the [`_lzSend`](<https://github.com/Tapioca-DAO/tapioca-sdk/blob/1eff367cd8660ecea4d5ed87184eb76c93791c96/src/contracts/lzApp/LzApp.sol#L49>) and extracting the gas passed from adapterParams with [`_getGasLimit`](<https://github.com/Tapioca-DAO/tapioca-sdk/blob/1eff367cd8660ecea4d5ed87184eb76c93791c96/src/contracts/lzApp/LzApp.sol#L63>) and validating that it is above some minimum threshold.

2. Another option is specifying the minimum gas for each and every packetType and enforcing it as such.

I would default to the first option because the issue is twofold since there is the minimum gas that is common for all the packets, but there is also the minimum gas per packet since each packet has a different payload size and data structure, and it is being differently decoded and handled.

Note: This also applies to the transaction which when received on the destination chain is supposed to send another message, this callback message should also be validated.

When it comes to the default implementations inside the [`OFTCoreV2`](<https://github.com/Tapioca-DAO/tapioca-sdk/blob/1eff367cd8660ecea4d5ed87184eb76c93791c96/src/contracts/token/oft/v2/OFTCoreV2.sol#L10>) there are two packet types [`PT_SEND`](<https://github.com/Tapioca-DAO/tapioca-sdk/blob/1eff367cd8660ecea4d5ed87184eb76c93791c96/src/contracts/token/oft/v2/OFTCoreV2.sol#L94>) and [`PT_SEND_AND_CALL`](<https://github.com/Tapioca-DAO/tapioca-sdk/blob/1eff367cd8660ecea4d5ed87184eb76c93791c96/src/contracts/token/oft/v2/OFTCoreV2.sol#L119>) and there is the available configuration of `useCustomAdapterParams` which can enforce the minimum gas passed. This should all be configured properly.
