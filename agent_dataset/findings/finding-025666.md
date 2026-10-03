---
id: 25666
severity: "Crit/High"
---

# TOFT removeCollateral can be used to steal all the balance

## Description



## Proof of Concept

The attack needs to be executed by invoking the [`removeCollateral`](<https://github.com/Tapioca-DAO/tapiocaz-audit/blob/master/contracts/tOFT/BaseTOFT.sol#L190>) function from any chain to chain on which the underlying balance resides, e.g. host chain of the TOFT. When the message is [received on the remote chain](<https://github.com/Tapioca-DAO/tapiocaz-audit/blob/master/contracts/tOFT/modules/BaseTOFTMarketModule.sol#L204-L258>), I have placed in the comments below what are the params that need to be passed to execute the attack.

```solidity
    function remove(bytes memory _payload) public {
    (
        ,
        ,
        address to,
        ,
        ITapiocaOFT.IRemoveParams memory removeParams,
        ICommonData.IWithdrawParams memory withdrawParams,
        ICommonData.IApproval[] memory approvals
    ) = abi.decode(
        _payload,
        (
            uint16,
            address,
            address,
            bytes32,
            ITapiocaOFT.IRemoveParams,
            ICommonData.IWithdrawParams,
            ICommonData.IApproval[]
        )
    );
    // approvals can be an empty array so this is skipped
    if (approvals.length > 0) {
        _callApproval(approvals);
    }

    // removeParams.market and removeParams.share don't matter
    approve(removeParams.market, removeParams.share);
    // removeParams.market just needs to be deployed by the attacker and do nothing, it is enough to implement IMarket interface
    IMarket(removeParams.market).removeCollateral(
        to,
        to,
        removeParams.share
    );

    // withdrawParams.withdraw =  true to enter the if block
    if (withdrawParams.withdraw) {
        // Attackers removeParams.market contract needs to have yieldBox() function and it can return any address
        address ybAddress = IMarket(removeParams.market).yieldBox();
        // Attackers removeParams.market needs to have collateralId() function and it can return any uint256
        uint256 assetId = IMarket(removeParams.market).collateralId();

        // removeParams.marketHelper is a malicious contract deployed by the attacker which is being transferred all the balance
        // withdrawParams.withdrawLzFeeAmount needs to be precomputed by the attacker to match the balance of TapiocaOFT
        IMagnetar(removeParams.marketHelper).withdrawToChain{
                value: withdrawParams.withdrawLzFeeAmount // This is not validated on the sending side so it can be any value
            }(
            ybAddress,
            to,
            assetId,
            withdrawParams.withdrawLzChainId,
            LzLib.addressToBytes32(to),
            IYieldBoxBase(ybAddress).toAmount(
                assetId,
                removeParams.share,
                false
            ),
            removeParams.share,
            withdrawParams.withdrawAdapterParams,
            payable(to),
            withdrawParams.withdrawLzFeeAmount
        );
    }
}
```

Neither `removeParams.marketHelper` or `withdrawParams.withdrawLzFeeAmount` are validated on the sending side so the former can be the address of a malicious contract and the latter can be the TOFT's balance of gas token.

This type of attack is possible because the `msg.sender` in `IMagnetar(removeParams.marketHelper).withdrawToChain` is the address of the TOFT contract which holds all the balances.

This is because:

1. Relayer submits the message to [`lzReceive`](<https://github.com/Tapioca-DAO/tapioca-sdk-audit/blob/90d1e8a16ebe278e86720bc9b69596f74320e749/src/contracts/lzApp/LzApp.sol#L35>) so he is the `msg.sender`.
2. Inside the [`_blockingLzReceive`](<https://github.com/Tapioca-DAO/tapioca-sdk-audit/blob/90d1e8a16ebe278e86720bc9b69596f74320e749/src/contracts/lzApp/NonblockingLzApp.sol#L25>) there is a call into its own public function so the `msg.sender` is the [address of the contract](<https://github.com/Tapioca-DAO/tapioca-sdk-audit/blob/90d1e8a16ebe278e86720bc9b69596f74320e749/src/contracts/lzApp/NonblockingLzApp.sol#L39>).
3. Inside the `_nonBlockingLzReceive` there is [delegatecall](<https://github.com/Tapioca-DAO/tapiocaz-audit/blob/master/contracts/tOFT/BaseTOFT.sol#L411>) into a corresponding module which preserves the `msg.sender` which is the address of the TOFT.
4. Inside the module there is a call to [withdrawToChain](<https://github.com/Tapioca-DAO/tapiocaz-audit/blob/master/contracts/tOFT/modules/BaseTOFTMarketModule.sol#L239>) and here the `msg.sender` is the address of the TOFT contract, so we can maliciously transfer all the balance of the TOFT.

## Recommendation

It's hard to recommend a simple fix since as I pointed out in my other issues the airdropping logic has many flaws. One of the ways of tackling this issue is during the [`removeCollateral`](<https://github.com/Tapioca-DAO/tapiocaz-audit/blob/master/contracts/tOFT/BaseTOFT.sol#L190>) to:

- Do not allow `adapterParams` params to be passed as bytes but rather as `gasLimit` and `airdroppedAmount`, from which you would encode either `adapterParamsV1` or `adapterParamsV2`.
- And then on the receiving side check and send with value only the amount the user has airdropped.
